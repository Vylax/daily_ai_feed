#!/usr/bin/env python3
# Simple script to test tutorial generation

from src.tutorial_generator import load_tutorial_topics, select_tutorial_topic, generate_tutorial
from src.config_loader import load_config
from src.processing import configure_gemini, reset_token_counts
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("Loading config...")
    config = load_config()
    
    print("Configuring Gemini...")
    configure_gemini(api_key=config.get('gemini_api_key'))
    
    reset_token_counts()
    
    print("Loading tutorial topics...")
    load_tutorial_topics(["LangGraph basics"])
    
    print("Selecting topic...")
    topic = select_tutorial_topic()
    print(f"Selected topic: {topic}")
    
    print("Generating tutorial...")
    result = generate_tutorial(topic, config)
    
    if result:
        print("Tutorial generation successful!")
        print(f"First 200 chars: {result[:200]}")
    else:
        print("Tutorial generation failed!")

if __name__ == "__main__":
    main() 