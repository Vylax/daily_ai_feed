# Project Context for AI Digest Actionable Ideas

## Project Camille: AI-Powered Email Management Assistant (Python, Natural Language Processing)
- **Goal:** Enhance email management by automating the organization, prioritization, and summarization of emails to improve user productivity.
- **Tech:** Python, Natural Language Processing (NLP), Machine Learning algorithms, secure email integration.
- **Data:** User email content, including metadata such as sender information, timestamps, and email body text.
- **Current Stage:** POC built, focusing on improving. The core functionalities—intelligent email sorting, automatic summarization, and strategic prioritization—are operational. The system is capable of analyzing emails to classify them by importance, provide concise summaries of lengthy messages, and organize emails into categories such as urgency, project, or action required. Future development aims to refine the AI models for enhanced accuracy and integrate with additional email platforms to broaden user accessibility. Need to train ML for sorting and filtering news and spam and also to predict mail priority, also need to implemetn the chatbot functionnalities to search the mails intuitively.

## Project Delta: AI-Powered Personalized Newsletter & Learning Hub  
- **Goal:** Stay up-to-date with the latest AI advancements, especially in LLMs and Google AI, while receiving custom tutorials and actionable insights to improve ongoing projects.  
- **Tech:** Python, RSS flux, LLM APIs (GPT-4, Gemini), Automated Content Generation (Markdown).  
- **Data:** AI research papers, blogs, Google AI updates, arXiv, Twitter/X feeds, newsletters, and technical documentation.  
- **Current Stage:**  
  - **News Aggregation:** Successfully curating and filtering daily AI news, with a focus on LLMs, Google AI, and emerging trends.  
  - **Custom Tutorials:** Automatically generating step-by-step guides based on chosen learning topics.  
  - **Actionable Insights:** Delivering practical takeaways to apply AI advancements directly to ongoing projects.  
  - **Next Steps:** Enhancing personalization with user feedback, improving summarization accuracy, and exploring multi-modal learning content (code snippets, video summaries).  

## Project Beta: Internal Knowledge Base Search (RAG - Retrieval-Augmented Generation)
- **Goal:** Allow employees to ask natural language questions about internal documentation.
- **Tech:** Python, LangChain/LlamaIndex, Vector Database (e.g., ChromaDB/FAISS), Sentence Transformers, LLM (e.g., Gemini/GPT-4).
- **Data:** Confluence pages, PDFs, Google Docs.
- **Current Stage:** POC built, focusing on improving retrieval accuracy and reducing hallucinations. Exploring different embedding models and chunking strategies.

## Project Gamma: Automated Content Summarization Service (API)
- **Goal:** Provide an API endpoint that accepts text or URLs and returns concise summaries.
- **Tech:** Python, FastAPI, Transformer models (e.g., PEGASUS, BART via Hugging Face).
- **Data:** External web articles, user-submitted text.
- **Current Stage:** Basic summarization working. Need to improve handling of very long documents and potentially add abstractive capabilities. Interested in evaluating newer summarization-focused models.