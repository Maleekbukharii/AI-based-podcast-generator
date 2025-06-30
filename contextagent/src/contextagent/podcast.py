import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from agents import Agent, Runner, trace
from dotenv import load_dotenv
from agents import set_default_openai_key
import openai

# Load environment variables
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
set_default_openai_key(api_key)

# Initialize OpenAI client for TTS
openai_client = openai.OpenAI(api_key=api_key)

# ========== DATA MODELS ==========

@dataclass
class PodcastParticipant:
    name: str
    role: str
    personality: str
    voice_id: str = "alloy"

@dataclass
class PodcastSegment:
    speaker: str
    content: str
    timestamp: float
    segment_type: str

# ========== PODCAST AGENTS ==========

participant_creator_agent = Agent(
    name="ParticipantCreator",
    instructions="""
You are a podcast participant creator. Given a topic and number of people, create diverse and interesting podcast participants.

ALWAYS include one HOST who guides the conversation.

For each participant, provide:
- name: A realistic, diverse name
- role: Their role (HOST, EXPERT, GUEST, RESEARCHER, ANALYST, etc.)
- personality: Brief but engaging personality description
- expertise: What they're known for related to the topic

Return ONLY a JSON array in this exact format:
[
    {
        "name": "Sarah Johnson",
        "role": "HOST", 
        "personality": "Engaging and curious, asks great questions",
        "expertise": "Professional podcast host with 5 years experience"
    },
    {
        "name": "Dr. Alex Chen",
        "role": "EXPERT", 
        "personality": "Knowledgeable but approachable, uses clear examples",
        "expertise": "Leading researcher in the field"
    }
]
"""
)

script_writer_agent = Agent(
    name="ScriptWriter",
    instructions="""
You are a professional podcast script writer. Create engaging, natural-sounding podcast scripts.

Your script should include:
1. Engaging introduction (2-3 minutes)
2. Natural, flowing conversation with multiple discussion points
3. Smooth transitions between topics
4. Host asking thoughtful questions
5. Guests providing expert insights and examples
6. Occasional light humor or personal anecdotes
7. Strong conclusion with key takeaways (2-3 minutes)

Format the script as:
[TIMESTAMP] SPEAKER_NAME: dialogue content here

Example:
[00:00] Sarah Johnson: Welcome to Tech Talk Today! I'm your host Sarah, and today we're diving into artificial intelligence with some amazing experts.

[00:15] Dr. Alex Chen: Thanks for having me, Sarah. I'm excited to discuss how AI is reshaping our world.

Make the conversation feel natural and engaging. Include realistic timing estimates.
"""
)

dialogue_enhancer_agent = Agent(
    name="DialogueEnhancer",
    instructions="""
You are a dialogue enhancement specialist. Take podcast scripts and make them more natural, engaging, and conversational.

Enhance scripts by:
- Adding natural speech patterns (um, well, you know)
- Including realistic interruptions and overlaps
- Adding emotional reactions (laughter, excitement, surprise)
- Making transitions smoother
- Adding follow-up questions
- Including personal examples and stories
- Making technical content more accessible

Keep the same structure but make it feel like a real conversation between real people.
"""
)

content_reviewer_agent = Agent(
    name="ContentReviewer",
    instructions="""
You are a podcast content reviewer. Review scripts for:

1. Content Quality:
   - Accuracy of information
   - Logical flow of ideas
   - Depth of discussion
   - Balance between speakers

2. Engagement:
   - Natural conversation flow
   - Appropriate pacing
   - Interesting examples
   - Clear explanations

3. Structure:
   - Strong opening and closing
   - Smooth transitions
   - Balanced speaker time
   - Appropriate length

Provide a brief review and suggest any improvements needed.
"""
)

# ========== AUDIO GENERATION UTILITIES ==========

try:
    from pydub import AudioSegment
    try:
        from pydub.silence import add_silence
    except ImportError:
        # add_silence is not always present in pydub, define a dummy if missing
        def add_silence(audio_segment, duration=1000):
            return audio_segment + AudioSegment.silent(duration=duration)
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("⚠️  PyDub not installed. Audio combining will be limited.")

class AudioGenerator:
    def __init__(self):
        self.voice_options = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
        self.speaker_voices = {}
        self.temp_files = []
    
    def assign_voices(self, participants: List[PodcastParticipant]) -> Dict[str, str]:
        """Assign unique voices to each participant"""
        for i, participant in enumerate(participants):
            voice = self.voice_options[i % len(self.voice_options)]
            self.speaker_voices[participant.name] = voice
        return self.speaker_voices
    
    async def generate_segment_audio(self, segment: PodcastSegment, temp_dir: str) -> str:
        """Generate audio for a single segment"""
        try:
            os.makedirs(temp_dir, exist_ok=True)
            
            voice = self.speaker_voices.get(segment.speaker, 'alloy')
            
            response = openai_client.audio.speech.create(
                model="tts-1",  # Use tts-1 as it's compatible with available voices
                voice=voice,
                input=segment.content,
                speed=1.0
            )
            
            # Create temp filename
            timestamp_clean = f"{int(segment.timestamp):04d}"
            filename = f"{temp_dir}/temp_seg_{timestamp_clean}.mp3"
            
            response.stream_to_file(filename)
            self.temp_files.append(filename)
            return filename
            
        except Exception as e:
            print(f"❌ Error generating audio for {segment.speaker}: {str(e)}")
            return None
    
    def combine_audio_segments(self, segment_files: List[str], output_filename: str, add_pauses: bool = True) -> str:
        """Combine multiple audio segments into a single file"""
        if not PYDUB_AVAILABLE:
            print("❌ PyDub not available. Cannot combine audio files.")
            return None
        
        try:
            combined = AudioSegment.empty()
            
            for i, file_path in enumerate(segment_files):
                if file_path and os.path.exists(file_path):
                    # Load the audio segment
                    segment = AudioSegment.from_mp3(file_path)
                    
                    # Add the segment to combined audio
                    combined += segment
                    
                    # Add a small pause between speakers (except for the last segment)
                    if add_pauses and i < len(segment_files) - 1:
                        pause = AudioSegment.silent(duration=500)  # 0.5 second pause
                        combined += pause
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_filename) or '.', exist_ok=True)
            
            # Export the combined audio
            combined.export(output_filename, format="mp3", bitrate="192k")
            print(f"✅ Combined audio saved: {output_filename}")
            
            return output_filename
            
        except Exception as e:
            print(f"❌ Error combining audio files: {str(e)}")
            return None
    
    def cleanup_temp_files(self):
        """Clean up temporary audio files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                print(f"⚠️ Could not remove temp file {temp_file}: {str(e)}")
        self.temp_files.clear()

# ========== ORCHESTRATOR CLASS ==========

class PodcastStudio:
    def __init__(self):
        self.audio_generator = AudioGenerator()
        self.participants = []
        self.script_segments = []
    
    async def create_participants(self, topic: str, num_people: int) -> List[PodcastParticipant]:
        """Create podcast participants using AI agent"""
        with trace("Creating Podcast Participants"):
            prompt = f"Create {num_people} podcast participants for a show about '{topic}'"
            
            result = await Runner.run(participant_creator_agent, input=prompt)
            
            try:
                participants_data = json.loads(result.final_output)
                self.participants = [
                    PodcastParticipant(
                        name=p["name"],
                        role=p["role"],
                        personality=p["personality"],
                        voice_id=self.audio_generator.voice_options[i % len(self.audio_generator.voice_options)]
                    )
                    for i, p in enumerate(participants_data)
                ]
                
                # Assign voices
                self.audio_generator.assign_voices(self.participants)
                
                return self.participants
                
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing participants JSON: {e}")
                return self._create_fallback_participants(topic, num_people)
    
    def _create_fallback_participants(self, topic: str, num_people: int) -> List[PodcastParticipant]:
        """Fallback participant creation"""
        participants = [
            PodcastParticipant("Alex Morgan", "HOST", "Professional and engaging", "alloy")
        ]
        
        names = ["Dr. Sarah Kim", "Michael Chen", "Lisa Rodriguez", "James Wilson"]
        roles = ["EXPERT", "RESEARCHER", "ANALYST", "GUEST"]
        
        for i in range(1, num_people):
            if i-1 < len(names):
                participants.append(
                    PodcastParticipant(
                        names[i-1], 
                        roles[i-1], 
                        f"Expert in {topic}",
                        self.audio_generator.voice_options[i % len(self.audio_generator.voice_options)]
                    )
                )
        
        self.participants = participants[:num_people]
        self.audio_generator.assign_voices(self.participants)
        return self.participants
    
    async def generate_script(self, topic: str, duration_minutes: int) -> List[PodcastSegment]:
        """Generate podcast script using AI agents"""
        with trace("Generating Podcast Script"):
            # Prepare context for script writer
            participants_info = "\n".join([
                f"- {p.name} ({p.role}): {p.personality}" 
                for p in self.participants
            ])
            
            script_prompt = f"""
Create a {duration_minutes}-minute podcast script about "{topic}".

Participants:
{participants_info}

The script should be natural, engaging, and informative with smooth conversation flow.
"""
            
            # Generate initial script
            script_result = await Runner.run(script_writer_agent, input=script_prompt)
            
            # Enhance the dialogue
            enhancement_prompt = f"""
Enhance this podcast script to make it more natural and engaging:

{script_result.final_output}

Topic: {topic}
Duration: {duration_minutes} minutes
"""
            
            enhanced_result = await Runner.run(dialogue_enhancer_agent, input=enhancement_prompt)
            
            # Parse script into segments
            self.script_segments = self._parse_script(enhanced_result.final_output)
            
            return self.script_segments
    
    def _parse_script(self, script_content: str) -> List[PodcastSegment]:
        """Parse script content into structured segments"""
        segments = []
        lines = script_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for timestamp and speaker patterns
            if ']' in line and ':' in line:
                try:
                    # Extract timestamp [MM:SS] or [HH:MM:SS]
                    timestamp_part = line[line.find('[')+1:line.find(']')]
                    time_parts = timestamp_part.split(':')
                    
                    if len(time_parts) == 2:  # MM:SS
                        minutes, seconds = map(int, time_parts)
                        timestamp = minutes * 60 + seconds
                    elif len(time_parts) == 3:  # HH:MM:SS
                        hours, minutes, seconds = map(int, time_parts)
                        timestamp = hours * 3600 + minutes * 60 + seconds
                    else:
                        timestamp = len(segments) * 30  # Fallback
                    
                    # Extract speaker and content
                    after_bracket = line[line.find(']')+1:].strip()
                    if ':' in after_bracket:
                        speaker, content = after_bracket.split(':', 1)
                        speaker = speaker.strip()
                        content = content.strip()
                        
                        # Determine segment type
                        segment_type = self._determine_segment_type(content, timestamp)
                        
                        segments.append(PodcastSegment(
                            speaker=speaker,
                            content=content,
                            timestamp=timestamp,
                            segment_type=segment_type
                        ))
                
                except (ValueError, IndexError):
                    continue  # Skip malformed lines
            
            # Alternative format: Speaker: content
            elif ':' in line and not line.startswith('#'):
                parts = line.split(':', 1)
                if len(parts) == 2:
                    speaker = parts[0].strip()
                    content = parts[1].strip()
                    timestamp = len(segments) * 30  # Rough estimate
                    
                    segment_type = self._determine_segment_type(content, timestamp)
                    
                    segments.append(PodcastSegment(
                        speaker=speaker,
                        content=content,
                        timestamp=timestamp,
                        segment_type=segment_type
                    ))
        
        return segments
    
    def _determine_segment_type(self, content: str, timestamp: float) -> str:
        """Determine segment type based on content and timing"""
        content_lower = content.lower()
        
        if timestamp < 180:  # First 3 minutes
            if any(word in content_lower for word in ['welcome', 'hello', 'introduction', 'today we']):
                return 'intro'
        elif timestamp > 1500:  # Last part
            if any(word in content_lower for word in ['thank you', 'thanks', 'wrap up', 'conclusion']):
                return 'outro'
        
        if any(word in content_lower for word in ['moving on', 'next topic', 'speaking of']):
            return 'transition'
        
        return 'discussion'
    
    async def review_content(self) -> str:
        """Review the generated content"""
        with trace("Reviewing Podcast Content"):
            script_text = "\n".join([
                f"[{seg.timestamp/60:.1f}min] {seg.speaker}: {seg.content}"
                for seg in self.script_segments
            ])
            
            review_prompt = f"""
Review this podcast script for quality, engagement, and structure:

{script_text[:2000]}...  # Truncated for brevity

Participants: {len(self.participants)}
Total segments: {len(self.script_segments)}
"""
            
            review_result = await Runner.run(content_reviewer_agent, input=review_prompt)
            return review_result.final_output
    
    async def generate_complete_podcast_audio(self, output_filename: str = None) -> str:
        """Generate a single complete podcast audio file"""
        with trace("Generating Complete Podcast Audio"):
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"podcast_complete_{timestamp}.mp3"
            
            temp_dir = "temp_audio_segments"
            segment_files = []
            
            print(f"🔊 Generating complete podcast audio...")
            print(f"   📁 Temp directory: {temp_dir}")
            print(f"   🎵 Output file: {output_filename}")
            
            try:
                # Generate audio for each segment
                for i, segment in enumerate(self.script_segments):
                    print(f"   🎤 Processing segment {i+1}/{len(self.script_segments)}: {segment.speaker}")
                    
                    temp_file = await self.audio_generator.generate_segment_audio(segment, temp_dir)
                    if temp_file:
                        segment_files.append(temp_file)
                    else:
                        print(f"   ⚠️  Skipped segment {i+1} due to error")
                
                # Combine all segments into one file
                if segment_files:
                    print(f"   🔗 Combining {len(segment_files)} audio segments...")
                    final_file = self.audio_generator.combine_audio_segments(
                        segment_files, 
                        output_filename,
                        add_pauses=True
                    )
                    
                    if final_file:
                        # Clean up temporary files
                        print(f"   🧹 Cleaning up temporary files...")
                        self.audio_generator.cleanup_temp_files()
                        
                        # Remove temp directory if empty
                        try:
                            os.rmdir(temp_dir)
                        except OSError:
                            pass  # Directory not empty or doesn't exist
                        
                        return final_file
                    else:
                        print("   ❌ Failed to combine audio segments")
                        return None
                else:
                    print("   ❌ No audio segments were generated successfully")
                    return None
                    
            except Exception as e:
                print(f"   ❌ Error during audio generation: {e}")
                # Clean up on error
                self.audio_generator.cleanup_temp_files()
                return None
    
    def export_script(self, filename: str = None) -> str:
        """Export script to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"podcast_script_{timestamp}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("AI GENERATED PODCAST SCRIPT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("PARTICIPANTS:\n")
            for p in self.participants:
                f.write(f"- {p.name} ({p.role}): {p.personality}\n")
            f.write("\n" + "=" * 50 + "\n\n")
            
            for segment in self.script_segments:
                mins = int(segment.timestamp // 60)
                secs = int(segment.timestamp % 60)
                f.write(f"[{mins:02d}:{secs:02d}] {segment.speaker}: {segment.content}\n\n")
        
        return filename
    
    def get_summary(self) -> Dict:
        """Get podcast summary statistics"""
        if not self.script_segments:
            return {"error": "No script generated"}
        
        total_duration = max([s.timestamp for s in self.script_segments]) if self.script_segments else 0
        speaker_stats = {}
        
        for segment in self.script_segments:
            if segment.speaker not in speaker_stats:
                speaker_stats[segment.speaker] = {"segments": 0, "words": 0}
            speaker_stats[segment.speaker]["segments"] += 1
            speaker_stats[segment.speaker]["words"] += len(segment.content.split())
        
        return {
            "total_duration_minutes": total_duration / 60,
            "total_segments": len(self.script_segments),
            "participants_count": len(self.participants),
            "speaker_statistics": speaker_stats,
            "participants": [
                {"name": p.name, "role": p.role, "voice": p.voice_id} 
                for p in self.participants
            ]
        }

# ========== MAIN ORCHESTRATION ==========

async def create_podcast(topic: str, num_people: int, duration_minutes: int) -> Dict:
    """Main function to orchestrate podcast creation"""
    studio = PodcastStudio()
    
    print(f"🎙️  Creating podcast: '{topic}'")
    print(f"👥 Participants: {num_people}")
    print(f"⏱️  Duration: {duration_minutes} minutes\n")
    
    # Step 1: Create participants
    print("1️⃣  Creating participants...")
    participants = await studio.create_participants(topic, num_people)
    print(f"   ✅ Created {len(participants)} participants:")
    for p in participants:
        print(f"      - {p.name} ({p.role}) - Voice: {p.voice_id}")
    print()
    
    # Step 2: Generate script
    print("2️⃣  Generating script...")
    segments = await studio.generate_script(topic, duration_minutes)
    print(f"   ✅ Generated {len(segments)} script segments")
    print()
    
    # Step 3: Review content
    print("3️⃣  Reviewing content...")
    review = await studio.review_content()
    print(f"   ✅ Content review completed")
    print(f"   📝 Review: {review[:100]}...")
    print()
    
    # Step 4: Export script
    print("4️⃣  Exporting script...")
    script_file = studio.export_script()
    print(f"   ✅ Script saved: {script_file}")
    print()
    
    # Step 5: Generate complete podcast audio
    print("5️⃣  Generating complete podcast audio...")
    podcast_audio_file = await studio.generate_complete_podcast_audio()
    if podcast_audio_file:
        print(f"   ✅ Complete podcast audio: {podcast_audio_file}")
    else:
        print(f"   ❌ Failed to generate complete audio file")
        podcast_audio_file = None
    print()
    
    # Step 6: Summary
    summary = studio.get_summary()
    
    return {
        "participants": participants,
        "script_segments": segments,
        "podcast_audio_file": podcast_audio_file,
        "script_file": script_file,
        "content_review": review,
        "summary": summary
    }

# ========== MAIN INTERACTIVE LOOP ==========

async def main():
    print("🎙️  Welcome to AI Podcast Generator!")
    print("=" * 50)
    print("Generate professional podcasts with AI agents")
    print("Type 'exit' to quit.\n")
    
    while True:
        try:
            print("📝 Enter podcast details:")
            
            topic = input("🎯 Topic: ").strip()
            if topic.lower() in ['exit', 'quit']:
                break
            if not topic:
                topic = "The Future of Technology"
            
            try:
                num_people = int(input("👥 Number of participants (2-5): ").strip() or "3")
                num_people = max(2, min(5, num_people))
            except ValueError:
                num_people = 3
            
            try:
                duration = int(input("⏱️  Duration in minutes (5-10): ").strip() or "30")
                duration = max(10, min(60, duration))
            except ValueError:
                duration = 30
            
            print(f"\n🚀 Starting podcast generation...\n")
            
            result = await create_podcast(topic, num_people, duration)
            
            print("🎉 PODCAST GENERATION COMPLETE!")
            print("=" * 50)
            summary = result['summary']
            print(f"📊 Summary:")
            print(f"   • Duration: {summary['total_duration_minutes']:.1f} minutes")
            print(f"   • Segments: {summary['total_segments']}")
            print(f"   • Participants: {summary['participants_count']}")
            print(f"   • Script file: {result['script_file']}")
            
            if result['podcast_audio_file']:
                print(f"   • 🎵 Complete podcast audio: {result['podcast_audio_file']}")
            else:
                print(f"   • ⚠️  Audio generation failed")
            
            print(f"\n👥 Participants:")
            for p in summary['participants']:
                print(f"   • {p['name']} ({p['role']}) - {p['voice']}")
            
            print(f"\n" + "=" * 50)
            
            continue_prompt = input("\n🔄 Generate another podcast? (y/n): ").strip().lower()
            if continue_prompt in ['n', 'no', 'exit', 'quit']:
                break
            print("\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again.\n")

if __name__ == "__main__":
    asyncio.run(main())