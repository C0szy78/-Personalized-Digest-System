# 📰 Personalized Digest System

A smart content curation system that uses AI to generate personalized article summaries based on member interests.

## 🌟 Features

1. **Member Onboarding with Interest Selection**
   - Register new members
   - Select interest tags during onboarding
   - Login to existing accounts

2. **Document Processing with AI (LLM Task #1)**
   - Upload articles, forum posts, or documents manually
   - **NEW: Fetch posts automatically from WordPress sites via REST API**
   - **NEW: Web scraping to extract clean content from post URLs**
   - Automatically extract relevant interest tags using Groq's LLM API
   - Analyze content and identify primary topics

3. **Personalized Digest Generation (LLM Task #2)**
   - Generate customized summaries for each member
   - Weight content based on matching interest tags
   - Store digests as drafts for review

4. **Interest Management**
   - Update interest preferences anytime
   - View digest statistics
   - Track published vs draft digests

5. **WordPress Integration**
   - Fetch posts from any WordPress site using REST API
   - Automatic web scraping of post content
   - Bulk processing of multiple posts
   - One-click integration with AI analysis

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```



### 3. Run the Application

```bash
streamlit run src/app.py
```

The application will open in your browser at `http://localhost:8501`

## 📖 How to Use

### Step 1: Member Onboarding
1. Go to **Member Onboarding** page
2. Register with your name and email
3. Select your interest tags (Technology, AI/ML, Health, Business, etc.)
4. Click Register

### Step 2: Upload Documents (Manual or WordPress)

#### Option A: Manual Upload
1. Go to **Upload Document** page
2. Enter document title and content
3. Select source type (Article/Forum/Document)
4. Click "Upload & Process"
5. The system will use **LLM Task #1** to extract interest tags
6. Generate personalized digests for all members

#### Option B: Fetch from WordPress
1. Go to **Fetch WordPress Posts** page
2. Enter WordPress site URL (e.g., https://domain1.badev.tools)
3. Set number of posts to fetch
4. Click "🔍 Fetch Posts"
5. The system will:
   - Fetch posts via WordPress REST API
   - Scrape clean content from each post URL
   - Display all posts with previews
6. Process individual posts or all at once
7. AI automatically extracts tags and generates digests

### Step 3: View Your Digests
1. Go to **View Digests** page
2. See all your personalized summaries
3. Digests are sorted by relevance to your interests
4. View matching interest tags
5. Publish or read full documents

### Step 4: Manage Interests
1. Go to **Manage Interests** page
2. Update your interest selections anytime
3. Future digests will reflect your new preferences

## 🤖 LLM Integration

The system uses Groq's LLM API (llama-3.3-70b-versatile) for two main tasks:

### LLM Task #1: Interest Tag Extraction
- **Input**: Raw document content + available interest tags
- **Process**: LLM analyzes content and identifies relevant categories
- **Output**: JSON with extracted tags, primary topic, and confidence level

### LLM Task #2: Personalized Digest Generation
- **Input**: Document content + member interests + extracted tags
- **Process**: LLM creates customized summary weighted by matching interests
- **Output**: Personalized summary text emphasizing relevant aspects

## 📊 Database Schema

- **Members**: User accounts with names and emails
- **Interests**: Predefined interest categories
- **Documents**: Uploaded content with extracted tags
- **Digests**: Personalized summaries for each member-document pair

## 🛠️ Technology Stack

- **Frontend**: Streamlit
- **Backend**: Python, SQLAlchemy
- **Database**: SQLite
- **LLM API**: Groq (llama-3.3-70b-versatile)
- **Libraries**: python-dotenv, pydantic

## 📂 Project Structure

```
tag_ai/
├── src/
│   ├── app.py           # Main Streamlit application
│   ├── database.py      # Database models and setup
│   ├── llm_service.py   # Groq LLM integration
│   └── __init__.py
├── .env                 # Environment variables (API key)
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 💡 Key Highlights

- ✅ **Two LLM Tasks**: Content analysis AND personalized summarization
- ✅ **Interest-based Weighting**: Summaries prioritize matching topics
- ✅ **Dynamic Preferences**: Update interests anytime
- ✅ **Draft System**: Review digests before publishing
- ✅ **Relevance Scoring**: Track how well content matches interests

## 🎯 Use Cases

- Personal news aggregation
- Research paper summaries
- Corporate knowledge sharing
- Educational content curation
- Community forum digests

