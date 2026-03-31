"""
RAG (Retrieval Augmented Generation) service.
Embeds repository code and retrieves relevant context for PR analysis.
"""

from typing import List, Dict, Any, Optional
from config import get_settings

settings = get_settings()


class RAGService:
    """
    Converts repository code into embeddings, stores them in pgvector,
    and retrieves relevant context when analyzing pull requests.
    """

    def __init__(self):
        self.embedding_model = settings.EMBEDDING_MODEL

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for a text chunk."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000],  # Truncate to model limit
            )
            return response.data[0].embedding
        except Exception:
            # Return zero vector as fallback
            return [0.0] * 1536

    async def index_repository(self, owner: str, repo: str, files: List[Dict[str, Any]]):
        """
        Index repository files by generating embeddings and storing in pgvector.
        """
        from database import async_session
        from models import CodeEmbedding, Repository
        from sqlalchemy import select

        async with async_session() as session:
            # Find repository
            result = await session.execute(
                select(Repository).where(
                    Repository.owner == owner,
                    Repository.name == repo,
                )
            )
            repository = result.scalar_one_or_none()
            if not repository:
                return

            for file_data in files:
                filename = file_data.get("filename", "")
                content = file_data.get("content", "")
                if not content:
                    continue

                # Split into chunks
                chunks = self._chunk_content(content)

                for i, chunk in enumerate(chunks):
                    embedding = await self.generate_embedding(
                        f"File: {filename}\n\n{chunk}"
                    )

                    code_embedding = CodeEmbedding(
                        file_path=filename,
                        chunk_index=i,
                        content=chunk,
                        embedding=embedding,
                        repository_id=repository.id,
                    )
                    session.add(code_embedding)

            await session.commit()

    async def retrieve_context(
        self,
        owner: str,
        repo: str,
        query: str,
        top_k: int = 5,
    ) -> str:
        """
        Retrieve relevant code context from pgvector for a given query.
        Uses cosine similarity search.
        """
        try:
            from database import async_session
            from models import CodeEmbedding, Repository
            from sqlalchemy import select

            query_embedding = await self.generate_embedding(query)

            async with async_session() as session:
                # Find repository
                result = await session.execute(
                    select(Repository).where(
                        Repository.owner == owner,
                        Repository.name == repo,
                    )
                )
                repository = result.scalar_one_or_none()
                if not repository:
                    return ""

                # Vector similarity search
                result = await session.execute(
                    select(CodeEmbedding)
                    .where(CodeEmbedding.repository_id == repository.id)
                    .order_by(CodeEmbedding.embedding.cosine_distance(query_embedding))
                    .limit(top_k)
                )
                embeddings = result.scalars().all()

                if not embeddings:
                    return ""

                # Format context
                context_parts = []
                for emb in embeddings:
                    context_parts.append(
                        f"### {emb.file_path} (chunk {emb.chunk_index})\n"
                        f"```\n{emb.content}\n```"
                    )

                return "\n\n".join(context_parts)

        except Exception:
            return ""

    def _chunk_content(self, content: str, chunk_size: int = 100, overlap: int = 20) -> List[str]:
        """Split content into overlapping chunks of lines."""
        lines = content.split('\n')
        chunks = []

        for i in range(0, len(lines), chunk_size - overlap):
            chunk = '\n'.join(lines[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)

        return chunks or [content]
