import os
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


def get_memory_file_path() -> str:
    """Get the memory file path from environment or use default."""
    path = os.getenv("MEMORY_FILE_PATH")
    if not path:
        # Default to ~/memory.md in user's home directory
        home_dir = os.path.expanduser("~")
        path = os.path.join(home_dir, "memory.md")
    else:
        # Expand ~ if present
        path = os.path.expanduser(path)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    return path


def add_memo(topic: str, content: str, tags: Optional[List[str]] = None) -> str:
    """
    Add a memo to the memory file.
    
    Args:
        topic: The topic or title of the memo
        content: The content/body of the memo
        tags: Optional list of tags for categorization
        
    Returns:
        Success message with location
    """
    memory_path = get_memory_file_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format tags
    tag_str = ""
    if tags:
        tag_str = f"  \nTags: {', '.join(f'#{tag}' for tag in tags)}"
    
    # Create memo entry
    memo = f"""
## {topic}
*Added: {timestamp}*{tag_str}

{content}

---
"""
    
    # Append to file
    with open(memory_path, "a", encoding="utf-8") as f:
        f.write(memo)
    
    return f"Memo added to {memory_path}"


def search_memos(query: str, max_results: int = 10) -> str:
    """
    Search through memos for a specific query.
    
    Args:
        query: The search query
        max_results: Maximum number of results to return
        
    Returns:
        Formatted search results
    """
    memory_path = get_memory_file_path()
    
    if not os.path.exists(memory_path):
        return "No memory file found. Start by adding a memo."
    
    with open(memory_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Split into sections (each memo starts with ##)
    sections = content.split("---")
    sections = [s.strip() for s in sections if s.strip()]
    
    results = []
    query_lower = query.lower()
    
    for section in sections[:max_results]:
        if query_lower in section.lower():
            results.append(section)
    
    if not results:
        return f"No memos found matching: {query}"
    
    return "\n\n---\n\n".join(results)


def list_memo_topics() -> str:
    """
    List all memo topics.
    
    Returns:
        List of all memo topics with timestamps
    """
    memory_path = get_memory_file_path()
    
    if not os.path.exists(memory_path):
        return "No memory file found. Start by adding a memo."
    
    with open(memory_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract topics (lines starting with ##)
    topics = []
    for line in content.split("\n"):
        if line.startswith("## "):
            topic = line[3:].strip()
            topics.append(topic)
    
    if not topics:
        return "No memos found."
    
    return "\n".join(f"- {topic}" for topic in topics)


def delete_memo(topic: str) -> str:
    """
    Delete a memo by topic.
    
    Args:
        topic: The topic of the memo to delete
        
    Returns:
        Result message
    """
    memory_path = get_memory_file_path()
    
    if not os.path.exists(memory_path):
        return "No memory file found."
    
    with open(memory_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find and remove the section
    sections = content.split("---")
    new_sections = []
    deleted = False
    
    for section in sections:
        if section.strip() and f"## {topic}" in section:
            deleted = True
            continue  # Skip this section
        new_sections.append(section)
    
    if not deleted:
        return f"No memo found with topic: {topic}"
    
    # Write back without the deleted section
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write("---".join(new_sections))
    
    return f"Deleted memo: {topic}"
