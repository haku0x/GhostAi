import json
import os
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, SlashOption
import google.generativeai as genai
from typing import Literal

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Configure bot
intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config['prefix'], intents=intents)

# Configure Gemini API
genai.configure(api_key=config['gemini_api_key'])
model = genai.GenerativeModel('gemini-2.0-flash')

# Store conversation history and personalities
conversation_history = {}
current_personality = {}

# Personality prompts
personalities = {
    "funny": "You are a funny and humorous assistant. Make jokes and use puns in your responses. Keep your tone light and entertaining.",
    "serious": "You are a serious and professional assistant. Provide factual and straightforward responses without humor or casual language.",
    "sarcastic": "You are a sarcastic assistant. Use dry humor and irony in your responses, but still be helpful.",
    "friendly": "You are a friendly and supportive assistant. Be warm, encouraging, and positive in your interactions."
}

# Default personality
DEFAULT_PERSONALITY = "friendly"

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    await bot.change_presence(activity=nextcord.Activity(
        type=nextcord.ActivityType.listening, 
        name=config['status']
    ))
    print('Bot is ready!')

# Create a slash command group
personality_group = bot.create_slash_command_group(
    name="personality",
    description="Commands to interact with the bot's personality"
)

@personality_group.subcommand(description="Change the bot's personality")
async def change(
    interaction: Interaction,
    personality: Literal["funny", "serious", "sarcastic", "friendly"] = SlashOption(
        description="Choose the bot's personality",
        required=True
    )
):
    user_id = str(interaction.user.id)
    current_personality[user_id] = personality
    
    embed = nextcord.Embed(
        title="Personality Changed",
        description=f"My personality has been changed to **{personality}**!",
        color=0x00ff00
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@personality_group.subcommand(description="View the bot's current personality")
async def current(interaction: Interaction):
    user_id = str(interaction.user.id)
    personality = current_personality.get(user_id, DEFAULT_PERSONALITY)
    
    embed = nextcord.Embed(
        title="Current Personality",
        description=f"My current personality is **{personality}**!",
        color=0x00ff00
    )
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@personality_group.subcommand(description="List all available personalities")
async def list(interaction: Interaction):
    embed = nextcord.Embed(
        title="Available Personalities",
        description="Here are all the personalities I can adopt:",
        color=0x00ff00
    )
    
    for name in personalities.keys():
        embed.add_field(name=name.capitalize(), value=personalities[name][:100] + "...", inline=False)
    
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    
    await interaction.response.send_message(embed=embed)

@bot.slash_command(description="Chat with the AI bot")
async def chat(
    interaction: Interaction,
    message: str = SlashOption(description="Your message to the bot", required=True)
):
    user_id = str(interaction.user.id)
    
    # Initialize conversation history if it doesn't exist
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    # Get current personality or use default
    personality = current_personality.get(user_id, DEFAULT_PERSONALITY)
    personality_prompt = personalities[personality]
    
    # Add user message to history
    conversation_history[user_id].append(f"User: {message}")
    
    # Keep only the last 10 messages to avoid token limits
    if len(conversation_history[user_id]) > 10:
        conversation_history[user_id] = conversation_history[user_id][-10:]
    
    # Create the prompt with personality and conversation history
    prompt = f"{personality_prompt}\n\nConversation history:\n"
    prompt += "\n".join(conversation_history[user_id])
    prompt += "\n\nAssistant:"
    
    # Let the user know we're processing
    await interaction.response.defer()
    
    try:
        # Generate response from Gemini
        response = model.generate_content(prompt)
        ai_response = response.text.strip()
        
        # Add AI response to history
        conversation_history[user_id].append(f"Assistant: {ai_response}")
        
        # Create embed response
        embed = nextcord.Embed(
            title=f"Chat ({personality.capitalize()} Mode)",
            description=ai_response,
            color=0x3498db
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.set_footer(text=f"Personality: {personality.capitalize()}")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = nextcord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

@bot.slash_command(description="Clear your conversation history with the bot")
async def clear_history(interaction: Interaction):
    user_id = str(interaction.user.id)
    
    if user_id in conversation_history:
        conversation_history[user_id] = []
        
        embed = nextcord.Embed(
            title="History Cleared",
            description="Your conversation history has been cleared!",
            color=0x00ff00
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
    else:
        embed = nextcord.Embed(
            title="No History",
            description="You don't have any conversation history to clear.",
            color=0xffff00
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)

@bot.slash_command(description="Get help with code in a specific language")
async def code_help(
    interaction: Interaction,
    language: str = SlashOption(description="The programming language you need help with", required=True),
    question: str = SlashOption(description="Your question about the code", required=True)
):
    user_id = str(interaction.user.id)

    # Get current personality or use default
    personality = current_personality.get(user_id, DEFAULT_PERSONALITY)
    personality_prompt = personalities[personality]

    prompt = f"{personality_prompt}\n\nThe user is asking for help with {language.upper()}.\n"
    prompt += f"User question: {question}\n\n"
    prompt += "Provide a helpful response with code examples. Format code properly with syntax highlighting. If providing a solution, explain how the code works step by step. If the user is asking about best practices, include modern approaches used in professional development."

    # Let the user know we're processing
    await interaction.response.defer()

    try:
        # Generate response from Gemini
        response = model.generate_content(prompt)
        ai_response = response.text.strip()

        # Create embed response
        embed = nextcord.Embed(
            title=f"Code Help ({language.capitalize()})",
            description=ai_response,
            color=0x3498db
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.set_footer(text=f"Personality: {personality.capitalize()}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        error_embed = nextcord.Embed(
            title="Error",
            description=f"An error occurred: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

# Run the bot
bot.run(config['token'])

