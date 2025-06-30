🎙️ AI Podcast Generator
A fully automated, end-to-end podcast creation system using LLM agents and OpenAI TTS. Generate professional podcasts from just a topic prompt — complete with scriptwriting, dialogue enhancement, content review, voice synthesis, and audio stitching.

🧠 Features
🤖 Multi-Agent Orchestration: Specialized agents for participant creation, script writing, enhancement, and review.

🗣️ Voice Synthesis: Uses OpenAI tts-1 voices (alloy, echo, fable, onyx, nova, shimmer) for each speaker.

📝 Script Generation: Structured and natural-sounding podcast scripts with speaker timestamps.

🔊 Audio Assembly: Combines individual segment audio into a full-length .mp3 podcast.

📊 Analytics: Provides a summary of total duration, segments, participants, and speaker stats.

🧹 Cleanup: Automatically removes temporary files after combining audio.

🚀 Getting Started
1. Clone the Repository

git clone https://github.com/Maleekbukharii/AI-based-podcast-generator
cd ai-podcast-generator

3. Install Dependencies
Ensure Python 3.8+ is installed.

Dependencies include:

openai

python-dotenv

pydub

asyncio

Your custom agents module (place it in the project)

3. Set Up Environment Variables
Create a .env file with your OpenAI API key:

OPENAI_API_KEY=sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXX
🛠️ Usage
Run the app interactively:

python your_main_script.py
Follow the prompts:

Enter podcast topic

Choose number of participants (2–5)

Choose duration (10–60 minutes)

Example:

🎯 Topic: Artificial Intelligence in Healthcare
👥 Number of participants (2-5): 3
⏱️  Duration in minutes (5-10): 20
The script will:

Generate participant personas

Write and enhance a podcast script

Review the content

Synthesize voice audio

Combine and export a full podcast .mp3

Output a .txt file with the script

📁 Outputs
podcast_script_YYYYMMDD_HHMMSS.txt	Full podcast script
podcast_complete_YYYYMMDD_HHMMSS.mp3	Final podcast audio
Temp audio files	Cleaned up after generation

🧪 Sample Agent Roles
ParticipantCreator: Designs fictional hosts, guests, and experts

ScriptWriter: Crafts an engaging, multi-speaker script

DialogueEnhancer: Makes the script more natural, lively, and human

ContentReviewer: Evaluates quality, structure, and engagement

🧠 Customization Tips
Modify AudioGenerator.voice_options to change voices.

Customize agent instructions for tone, style, or format.

Extend orchestration with background music, sound effects, or multilingual support.

⚠️ Notes
Ensure ffmpeg is installed and available in PATH (required by pydub).

The agents module must define Agent, Runner, and trace.

TTS generation is billed per character by OpenAI; usage may incur costs.


💡 Credits
Created by Maleekbukharii
Built with ❤️ using OpenAI APIs and Python asyncio
