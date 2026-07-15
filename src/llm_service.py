"""LLM service for content analysis and digest generation using Groq API."""
import os
import json
from typing import List, Dict
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class LLMService:
    """Service for interacting with Groq LLM API."""
    
    def __init__(self):
        """Initialize Groq client."""
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
    
    def extract_interest_tags(self, content: str, available_tags: List[str]) -> Dict:
        """
        LLM Task 1: Extract relevant interest tags from document content.
        
        Args:
            content: The document content to analyze
            available_tags: List of available interest tag names
            
        Returns:
            Dict with extracted tags and confidence scores
        """
        prompt = f"""Analyze the following content and identify which interest categories it relates to.

Available interest categories: {', '.join(available_tags)}

Content to analyze:
{content[:3000]}  # Limit content length

Please respond with a JSON object containing:
1. "tags": A list of relevant interest tags from the available categories
2. "primary_topic": The main topic/theme of the content
3. "confidence": Your confidence level (high/medium/low)

Respond ONLY with valid JSON, no other text."""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content analyzer. Respond only with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
            )
            
            response_text = chat_completion.choices[0].message.content

            # Clean response - sometimes LLM adds markdown code blocks
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            result = json.loads(response_text)
            return result
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in extract_interest_tags: {e}")
            print(f"Raw response: {response_text[:200]}")
            return {"tags": [], "primary_topic": "Unknown", "confidence": "low"}
        except Exception as e:
            print(f"Error in extract_interest_tags: {e}")
            return {"tags": [], "primary_topic": "Unknown", "confidence": "low"}
    
    def generate_personalized_digest(
        self, 
        content: str, 
        title: str,
        member_interests: List[str],
        document_tags: List[str]
    ) -> str:
        """
        LLM Task 2: Generate a personalized summary/digest based on member interests.
        
        Args:
            content: The document content
            title: Document title
            member_interests: List of member's interest tags
            document_tags: List of tags extracted from the document
            
        Returns:
            Personalized summary text
        """
        # Calculate overlap for relevance weighting
        matching_tags = set(member_interests) & set(document_tags)
        
        prompt = f"""Create a personalized summary of the following article for a reader interested in: {', '.join(member_interests)}.

Article Title: {title}

Article Content:
{content[:4000]}  # Limit content length

Instructions:
1. Focus on aspects related to the reader's interests: {', '.join(member_interests)}
2. This article has been tagged with: {', '.join(document_tags)}
3. Matching interests: {', '.join(matching_tags) if matching_tags else 'None - provide general summary'}
4. If there are matching interests, emphasize those aspects heavily
5. Keep the summary concise (3-5 paragraphs)
6. Include key takeaways relevant to the reader's interests

Generate a compelling, personalized summary:"""

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert content curator who creates personalized summaries."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model=self.model,
                temperature=0.5,
            )
            
            summary = chat_completion.choices[0].message.content
            return summary
        except Exception as e:
            print(f"Error in generate_personalized_digest: {e}")
            return f"Error generating summary: {str(e)}"
    
    def test_connection(self) -> bool:
        """Test the Groq API connection."""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": "Say 'connected' if you can read this."
                    }
                ],
                model=self.model,
            )
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
