import discord 
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import asyncio
import datetime
import os
import json
from io import BytesIO, StringIO
from PIL import Image, ImageDraw, ImageFont
import requests
from dotenv import load_dotenv
import csv

load_dotenv()  # Load environment variables from .env file
TOKEN = os.getenv('DISCORD_TOKEN')

# Config functions
def load_config():
    """Load configuration from JSON file"""
    config_path = "bot_config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}  # Return empty dict if file doesn't exist

def save_config(config):
    """Save configuration to JSON file"""
    config_path = "bot_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')

# ...existing code...

@bot.command()
@commands.has_permissions(administrator=True)
async def clone_server(ctx, source_guild_id: int, target_guild_id: int):
    # Get source and target guilds
    source_guild = bot.get_guild(source_guild_id)
    target_guild = bot.get_guild(target_guild_id)
    
    if not source_guild or not target_guild:
        await ctx.send("Could not find one or both servers.")
        return

    # Clone roles
    roles = list(source_guild.roles)  # Convert to list
    roles.reverse() # To create roles in correct order
    role_mapping = {}
    
    # ...rest of the code remains the same...
    
    for role in roles:
        if role.name != "@everyone":
            try:
                new_role = await target_guild.create_role(
                    name=role.name,
                    permissions=role.permissions,
                    color=role.color,
                    hoist=role.hoist,
                    mentionable=role.mentionable
                )
                role_mapping[role.id] = new_role.id
                await asyncio.sleep(1)
            except discord.Forbidden:
                await ctx.send(f"Could not create role {role.name}")

    # Clone categories and channels
    for category in source_guild.categories:
        try:
            new_category = await target_guild.create_category(
                name=category.name,
                overwrites=category.overwrites
            )
            
            for channel in category.channels:
                if isinstance(channel, discord.TextChannel):
                    await target_guild.create_text_channel(
                        name=channel.name,
                        category=new_category,
                        topic=channel.topic,
                        slowmode_delay=channel.slowmode_delay,
                        nsfw=channel.nsfw,
                        position=channel.position
                    )
                elif isinstance(channel, discord.VoiceChannel):
                    await target_guild.create_voice_channel(
                        name=channel.name,
                        category=new_category,
                        bitrate=channel.bitrate,
                        user_limit=channel.user_limit,
                        position=channel.position
                    )
            await asyncio.sleep(1)
        except discord.Forbidden:
            await ctx.send(f"Could not create category {category.name}")

    # Clone channels without category
    for channel in source_guild.channels:
        if not channel.category:
            try:
                if isinstance(channel, discord.TextChannel):
                    await target_guild.create_text_channel(name=channel.name)
                elif isinstance(channel, discord.VoiceChannel):
                    await target_guild.create_voice_channel(name=channel.name)
                await asyncio.sleep(1)
            except discord.Forbidden:
                await ctx.send(f"Could not create channel {channel.name}")

    await ctx.send("Server clone completed!")
@bot.command()
@commands.has_permissions(administrator=True)
async def massdm(ctx, *, message):
    """Send a DM to all members in the server. Only usable by administrators."""
    sent = 0
    failed = 0
    
    # Inform that the process is starting
    await ctx.send(f"Starting to send messages to all members in {ctx.guild.name}.")
    
    # Progress message
    status_message = await ctx.send("Sending messages... 0% complete")
    
    total_members = len(ctx.guild.members)
    
    for i, member in enumerate(ctx.guild.members):
        # Skip bots
        if member.bot:
            continue
            
        try:
            await member.send(f"Message from {ctx.guild.name} :\n{message}")
            sent += 1
            
            # Update progress every 10 members or so
            if i % 10 == 0 or i == total_members - 1:
                await status_message.edit(content=f"Sending messages... {round((i+1)/total_members*100)}% complete")
                
        except (discord.Forbidden, discord.HTTPException):
            failed += 1
        
        # Rate limiting to avoid hitting Discord's rate limits
        await asyncio.sleep(1)
    
    await ctx.send(f"Mass DM complete. Successfully sent to {sent} members. Failed to send to {failed} members.")


@bot.event
async def on_member_join(member):
    """Send a welcome message with custom image when a member joins"""
    # Load config to get welcome channel
    config = load_config()
    welcome_channel_id = config.get("welcome_channel")
    
    if not welcome_channel_id:
        return  # No welcome channel configured
        
    welcome_channel = member.guild.get_channel(int(welcome_channel_id))
    if not welcome_channel:
        return
    
    # Create welcome image
    img = await create_welcome_image(member)
    
    # Send the welcome message with the image
    file = discord.File(fp=img, filename="welcome.png")
    await welcome_channel.send(f"Welcome to the server, {member.mention}!", file=file)

async def create_welcome_image(member):
    """Create a custom welcome image"""
    # Load the background image
    background_path = "welcome_background.png"  # Save your background image with this name
    
    try:
        img = Image.open(background_path)
    except FileNotFoundError:
        # Create a simple background if image doesn't exist
        img = Image.new('RGB', (800, 300), color=(54, 57, 63))
    
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts - use default if not available
    try:
        title_font = ImageFont.truetype("/fonts/RobotoSlab-Regular.ttf", 55)
        subtitle_font = ImageFont.truetype("arial.ttf", 40)
    except IOError:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
    
    # Adjusted positions - moved text even lower on the image
    draw.text((350, 220), f"Welcome to {member.guild.name}", fill=(0, 0, 0), font=title_font, anchor="mm")
    draw.text((295, 290), f"{member.name}", fill=(43, 117, 156), font=subtitle_font, anchor="mm")
    # Try to add user avatar
    try:
        # Get avatar URL and download
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        response = requests.get(avatar_url)
        avatar = Image.open(BytesIO(response.content))
        avatar = avatar.resize((200, 200))
        
        # Make avatar circular
        mask = Image.new('L', avatar.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 200, 200), fill=255)
        
        # Position avatar on right side
        img.paste(avatar, (740, 150), mask)
    except Exception as e:
        print(f"Error adding avatar: {e}")
    
    # Save to buffer
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer

# Add command to setup welcome channel
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_welcome(ctx, channel: discord.TextChannel = None):
    """Set up the welcome channel for new member messages"""
    if not channel:
        channel = ctx.channel
    
    config = load_config()
    config["welcome_channel"] = channel.id
    save_config(config)
    
    await ctx.send(f"Welcome channel set to {channel.mention}!")

    # Add this import if it's not already there
import typing

# Role Selection System
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_role_selection(ctx, channel: discord.TextChannel = None):
    """Creates a pinned embed message with reactions for selecting Participant or Organisateur roles"""
    if not channel:
        channel = ctx.channel
    
    config = load_config()
    
    # Initialize role selector configuration
    if "role_selector" not in config:
        config["role_selector"] = {}
    
    # Create embed
    embed = discord.Embed(
        title="Select Your Role",
        description="React below to select your role in the server!\n\n"
                  "🔵 - Participant\n"
                  "🔴 - Organisateur\n\n"
                  "Click on the reaction that corresponds to your role.",
        color=discord.Color.gold(),
        stamp=datetime.datetime.now()
    )
    
    embed.set_footer(text=f"Role Selection | {ctx.guild.name}")
    
    # Send and pin the message in the selected channel
    message = await channel.send(embed=embed)
    await message.pin()
    
    # Add the reactions
    await message.add_reaction("🔵")  # For Participant
    await message.add_reaction("🔴")  # For Organisateur
    
    # Store message info in config
    config["role_selector"]["message_id"] = message.id
    config["role_selector"]["channel_id"] = channel.id
    
    # Find or create the roles
    participant_role = discord.utils.get(ctx.guild.roles, name="Participant")
    if not participant_role:
        participant_role = await ctx.guild.create_role(
            name="Participant",
            color=discord.Color.blue(),
            reason="Auto-created for role selection"
        )
        
    organisateur_role = discord.utils.get(ctx.guild.roles, name="Organisateur")
    if not organisateur_role:
        organisateur_role = await ctx.guild.create_role(
            name="Organisateur",
            color=discord.Color.red(),
            reason="Auto-created for role selection"
        )
    
    # Store role IDs in config
    config["role_selector"]["participant_role_id"] = participant_role.id
    config["role_selector"]["organisateur_role_id"] = organisateur_role.id
    save_config(config)
    
    await ctx.send(f"Role selection message created and pinned in {channel.mention}!")

# Add handlers for the role selection reactions
@bot.event
async def on_raw_reaction_add(payload):
    """Handle reaction adds for both channel selector and role selection"""
    # Ignore bot reactions
    if payload.member.bot:
        return
    
    config = load_config()
    
    # First check if it's a channel selector reaction
    channel_selector = config.get("channel_selector", {})
    if str(payload.message_id) == str(channel_selector.get("message_id")):
        # Handle channel selection (existing code)
        emoji_id = str(payload.emoji.id) if payload.emoji.id else payload.emoji.name
        emoji_role_pairs = channel_selector.get("emoji_role_pairs", {})
        
        if emoji_id in emoji_role_pairs:
            role_id = emoji_role_pairs[emoji_id]["role_id"]
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            
            if role:
                try:
                    await payload.member.add_roles(role, reason="Channel selection")
                    # Get channel object
                    channel = guild.get_channel(emoji_role_pairs[emoji_id]["channel_id"])
                    if channel:
                        try:
                            await payload.member.send(f"You now have access to the #{channel.name} channel!")
                        except discord.Forbidden:
                            pass  # Can't DM user
                except discord.Forbidden:
                    print(f"Missing permissions to add role {role.name}")
        return
    
    # Check if it's a role selector reaction
    role_selector = config.get("role_selector", {})
    if str(payload.message_id) != str(role_selector.get("message_id")):
        return
    
    guild = bot.get_guild(payload.guild_id)
    emoji_name = payload.emoji.name
    
    # Handle the role selection
    if emoji_name == "🔵":  # Participant
        role_id = role_selector.get("participant_role_id")
        role = guild.get_role(int(role_id))
        if role:
            try:
                await payload.member.add_roles(role, reason="Selected Participant role")
                try:
                    await payload.member.send("You have been assigned the Participant role!")
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                print("Missing permissions to add Participant role")
    
    elif emoji_name == "🔴":  # Organisateur
        role_id = role_selector.get("organisateur_role_id")
        role = guild.get_role(int(role_id))
        if role:
            try:
                await payload.member.add_roles(role, reason="Selected Organisateur role")
                try:
                    team_msg = await payload.member.send("You have been assigned the Organisateur role! Please reply with your team name to create or join a team.")
                    
                    def check(m):
                        return m.author.id == payload.user_id and isinstance(m.channel, discord.DMChannel)
                    
                    try:
                        team_response = await bot.wait_for('message', check=check, timeout=10.0)
                        team_name = team_response.content.strip()
                        
                        if team_name:
                            # Get the guild
                            guild = bot.get_guild(payload.guild_id)
                            
                            # Check if team role exists, create if it doesn't
                            team_role = discord.utils.get(guild.roles, name=team_name)
                            if not team_role:
                                team_role = await guild.create_role(
                                    name=team_name,
                                    color=discord.Color.green(),
                                    reason=f"Team created by {payload.member.name}"
                                )
                                await payload.member.send(f"Created new team: {team_name}")
                            
                            # Assign the role
                            await payload.member.add_roles(team_role, reason=f"Joined team {team_name}")
                            await payload.member.send(f"You have been added to team: {team_name}")
                    except asyncio.TimeoutError:
                        await payload.member.send("You didn't provide a team name in time. You can use a command later to join a team.")
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                print("Missing permissions to add Organisateur role")

# Modify the existing on_raw_reaction_remove to handle both systems
@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction removes for both channel selector and role selection"""
    config = load_config()
    
    # First check if it's a channel selector reaction
    channel_selector = config.get("channel_selector", {})
    if str(payload.message_id) == str(channel_selector.get("message_id")):
        # Existing channel selection removal code
        emoji_id = str(payload.emoji.id) if payload.emoji.id else payload.emoji.name
        emoji_role_pairs = channel_selector.get("emoji_role_pairs", {})
        
        if emoji_id in emoji_role_pairs:
            role_id = emoji_role_pairs[emoji_id]["role_id"]
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            
            if role and member and not member.bot:
                try:
                    await member.remove_roles(role, reason="Channel selection removed")
                except discord.Forbidden:
                    print(f"Missing permissions to remove role {role.name}")
        return
    
    # Check if it's a role selector reaction
    role_selector = config.get("role_selector", {})
    if str(payload.message_id) != str(role_selector.get("message_id")):
        return
    
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    
    emoji_name = payload.emoji.name
    
    # Handle the role removal
    if emoji_name == "🔵":  # Participant
        role_id = role_selector.get("participant_role_id")
        role = guild.get_role(int(role_id))
        if role:
            try:
                await member.remove_roles(role, reason="Removed Participant role")
            except discord.Forbidden:
                print("Missing permissions to remove Participant role")
    
    elif emoji_name == "🔴":  # Organisateur
        role_id = role_selector.get("organisateur_role_id")
        role = guild.get_role(int(role_id))
        if role:
            try:
                await member.remove_roles(role, reason="Removed Organisateur role")
            except discord.Forbidden:
                print("Missing permissions to remove Organisateur role")
            
# Add these imports at the top if they're not already there
from discord import Activity, ActivityType, Status
import datetime
import asyncio
import os
import json

# Activity commands
@bot.command()
@commands.has_permissions(administrator=True)
async def set_activity(ctx, activity_type, *, text):
    """
    Set the bot's activity status
    Types: playing, watching, listening, streaming, competing
    """
    activity_types = {
        "playing": ActivityType.playing,
        "watching": ActivityType.watching,
        "listening": ActivityType.listening,
        "streaming": ActivityType.streaming,
        "competing": ActivityType.competing
    }
    
    activity_type = activity_type.lower()
    if activity_type not in activity_types:
        await ctx.send(f"Invalid activity type. Choose from: {', '.join(activity_types.keys())}")
        return
    
    activity = Activity(type=activity_types[activity_type], name=text)
    await bot.change_presence(activity=activity)
    
    # Save to config
    config = load_config()
    config["bot_activity"] = {
        "type": activity_type,
        "text": text
    }
    save_config(config)
    
    await ctx.send(f"Activity set to: {activity_type} {text}")

@bot.command()
@commands.has_permissions(administrator=True)
async def set_status(ctx, status):
    """Set bot's status (online, idle, dnd, invisible)"""
    statuses = {
        "online": Status.online,
        "idle": Status.idle,
        "dnd": Status.dnd,
        "invisible": Status.invisible
    }
    
    status = status.lower()
    if status not in statuses:
        await ctx.send(f"Invalid status. Choose from: {', '.join(statuses.keys())}")
        return
    
    # Get current activity if any
    config = load_config()
    activity_config = config.get("bot_activity", {})
    
    activity = None
    if activity_config:
        activity_types = {
            "playing": ActivityType.playing,
            "watching": ActivityType.watching,
            "listening": ActivityType.listening,
            "streaming": ActivityType.streaming,
            "competing": ActivityType.competing
        }
        activity = Activity(
            type=activity_types.get(activity_config.get("type", "playing")), 
            name=activity_config.get("text", "")
        )
    
    await bot.change_presence(status=statuses[status], activity=activity)
    
    # Save to config
    config["bot_status"] = status
    save_config(config)
    
    await ctx.send(f"Status set to: {status}")

# Timer command - integrating with your existing code
@bot.command()
async def timer(ctx, hours: int = 0, minutes: int = 0):
    """Create a countdown timer"""
    if hours == 0 and minutes == 0:
        await ctx.send("Please specify time in hours and/or minutes!")
        return
    
    total_seconds = (hours * 3600) + (minutes * 60)
    end_time = datetime.datetime.now() + datetime.timedelta(seconds=total_seconds)
    
    # Create an embed for the timer
    embed = discord.Embed(
        title="⏱️ Timer Started",
        description=f"Time remaining: {hours:02d}:{minutes:02d}:00",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=f"Timer requested by {ctx.author}")
    
    # Initial message
    message = await ctx.send(embed=embed)
    
    # Update the timer every second
    while datetime.datetime.now() < end_time:
        time_left = end_time - datetime.datetime.now()
        hours_left = int(time_left.total_seconds() // 3600)
        minutes_left = int((time_left.total_seconds() % 3600) // 60)
        seconds_left = int(time_left.total_seconds() % 60)
        
        # Update the embed
        embed.description = f"Time remaining: {hours_left:02d}:{minutes_left:02d}:{seconds_left:02d}"
        
        # Update color based on time left (changes to yellow at 25%, red at 10%)
        percentage_left = time_left.total_seconds() / total_seconds
        if percentage_left <= 0.1:
            embed.color = discord.Color.red()
        elif percentage_left <= 0.25:
            embed.color = discord.Color.gold()
        
        await message.edit(embed=embed)
        await asyncio.sleep(1)
    
    # Timer finished
    finish_embed = discord.Embed(
        title="⏰ Time's Up!",
        description="The timer has ended.",
        color=discord.Color.red(),
        timestamp=datetime.datetime.now()
    )
    finish_embed.set_footer(text=f"Timer requested by {ctx.author}")
    
    await message.edit(embed=finish_embed)
    await ctx.send(f"{ctx.author.mention} Your timer has finished!")

# Modify your on_ready event to set the saved activity
@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    
    # Load activity and status from config
    config = load_config()
    activity_config = config.get("bot_activity", {})
    status_config = config.get("bot_status", "online")
    
    # Set activity if configured
    if activity_config:
        activity_types = {
            "playing": ActivityType.playing,
            "watching": ActivityType.watching,
            "listening": ActivityType.listening,
            "streaming": ActivityType.streaming,
            "competing": ActivityType.competing
        }
        
        activity_type = activity_config.get("type", "playing")
        activity_text = activity_config.get("text", "")
        
        activity = Activity(
            type=activity_types.get(activity_type, ActivityType.playing),
            name=activity_text
        )
        
        # Set status
        status_options = {
            "online": Status.online,
            "idle": Status.idle,
            "dnd": Status.dnd,
            "invisible": Status.invisible
        }
        
        await bot.change_presence(
            status=status_options.get(status_config, Status.online),
            activity=activity
        )

        # Add these imports at the top of your file


# Form registration system
class TeamRegistrationForm(Modal):
    def __init__(self):
        super().__init__(title="Team Registration")
        
        self.name_input = TextInput(
            label="Your Full Name",
            placeholder="Enter your Full Name",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)
        
        self.team_input = TextInput(
            label="Your Team Name",
            placeholder="Enter your TEAM Name",
            required=True,
            max_length=100
        )
        self.add_item(self.team_input)


    async def on_submit(self, interaction: discord.Interaction):
        # Extract values
        user_name = self.name_input.value.strip()
        team_name = self.team_input.value.strip()
        
        # Get config and initialize registrations if not exists
        config = load_config()
        if "registrations" not in config:
            config["registrations"] = []
        
        # Store registration data
        registration_data = {
            "user_id": interaction.user.id,
            "user_discord_name": interaction.user.name,
            "provided_name": user_name,
            "team_name": team_name,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        config["registrations"].append(registration_data)
        save_config(config)
        
        # Check if team role exists
        guild = interaction.guild
        team_role = discord.utils.get(guild.roles, name=team_name)
        role_created = False
        
        if not team_role:
            # Create the team role
            try:
                team_role = await guild.create_role(
                    name=team_name,
                    color=discord.Color.random(),
                    reason=f"Team created for {user_name}"
                )
                role_created = True
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to create roles.", ephemeral=True)
                return
            
        # Assign the role silently
        try:
            await interaction.user.add_roles(team_role, reason=f"Registered for team {team_name}")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to assign roles.", ephemeral=True)
            return
            
        # Send confirmation message
        if role_created:
            await interaction.response.send_message(
                f"Thank you for registering, **{user_name}**! 🤗 ", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Thank you for registering, {user_name}! You've been assigned to team **{team_name}**.", 
                ephemeral=True
            )

class RegistrationButton(View):
    def __init__(self):
        super().__init__(timeout=None)  # The button never times out
    
    @discord.ui.button(label="Register for a Team", style=discord.ButtonStyle.primary, custom_id="register_team_button")
    async def register_button_callback(self, interaction, button):
        # Show the registration form modal
        modal = TeamRegistrationForm()
        await interaction.response.send_modal(modal)

# Setup command to create the registration form
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_registration(ctx, channel: discord.TextChannel = None):
    """Creates a form with a button for team registration"""
    if not channel:
        channel = ctx.channel
    
    # Create the embed
    embed = discord.Embed(
        title="Team Registration",
        description="Click the button below to register for a team.\n\n"
                  "You'll be asked to provide:\n"
                  "• Your full name\n"
                  "• Your team name\n\n"
                  "After registration, Check your role if you have new role Team Name",
        color=discord.Color.blue()
    )
    
    # Add the button view
    view = RegistrationButton()
    
    # Send the message with the button
    message = await channel.send(embed=embed, view=view)
    
    # Store message info in config
    config = load_config()
    config["registration_form"] = {
        "message_id": message.id,
        "channel_id": channel.id
    }
    save_config(config)
    
    await ctx.send(f"Registration form has been set up in {channel.mention}.")


# Command to export registrations as CSV
@bot.command()
@commands.has_permissions(administrator=True)
async def export_registrations(ctx, channel: discord.TextChannel = None):
    """Exports all team registrations as a CSV file"""
    if not channel:
        channel = ctx.channel
    
    # Load registrations data
    config = load_config()
    registrations = config.get("registrations", [])
    
    if not registrations:
        await ctx.send("No registrations found!")
        return
    
    # Create CSV in memory
    output = StringIO()
    csv_writer = csv.writer(output)
    
    # Write headers
    csv_writer.writerow([
        "Discord User ID", 
        "Discord Username", 
        "Provided Name", 
        "Team Name", 
        "Registration Date"
    ])
    
    # Write data rows
    for reg in registrations:
        csv_writer.writerow([
            reg.get("user_id", ""),
            reg.get("user_discord_name", ""),
            reg.get("provided_name", ""),
            reg.get("team_name", ""),
            reg.get("timestamp", "")
        ])
    
    # Reset the position to the beginning of the buffer
    output.seek(0)
    
    # Create a file to send
    file = discord.File(
        fp=StringIO(output.getvalue()),
        filename=f"team_registrations_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    
    # Send the file
    await channel.send("Here are the team registrations:", file=file)

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    
    config = load_config()
    if "registration_form" in config:
        bot.add_view(RegistrationButton())

# Add these imports at the top of your file if needed
from discord.ui import Button, View, Modal, TextInput
import asyncio

# Ticket System UI Components
class TicketButton(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Create Support Ticket", style=discord.ButtonStyle.green, emoji="🎫", custom_id="create_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button):
        # Check if user already has a ticket open
        config = load_config()
        tickets = config.get("tickets", {})
        
        # Check for existing ticket by this user
        user_id = str(interaction.user.id)
        for ticket_id, ticket_data in tickets.items():
            if ticket_data.get("creator_id") == user_id and not ticket_data.get("closed", False):
                existing_channel = interaction.guild.get_channel(int(ticket_data.get("channel_id")))
                if existing_channel:
                    await interaction.response.send_message(
                        f"You already have an open ticket: {existing_channel.mention}",
                        ephemeral=True
                    )
                    return
        
        # Open a ticket form
        ticket_modal = TicketCreationModal()
        await interaction.response.send_modal(ticket_modal)

class TicketCreationModal(Modal):
    def __init__(self):
        super().__init__(title="Create Support Ticket")
        
        self.subject = TextInput(
            label="Ticket Subject",
            placeholder="What is your question or issue about?",
            required=True,
            max_length=100
        )
        self.add_item(self.subject)
        
        self.description = TextInput(
            label="Description",
            placeholder="Please describe your issue in detail...",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        # Load configuration
        config = load_config()
        if "tickets" not in config:
            config["tickets"] = {}
        
        # Get the support role
        support_role_id = config.get("support_role_id")
        support_role = None
        if support_role_id:
            support_role = interaction.guild.get_role(int(support_role_id))
        
        # Create ticket channel name
        ticket_id = len(config["tickets"]) + 1
        channel_name = f"ticket-{ticket_id:04d}-{interaction.user.name}"
        
        # Set permissions for the channel
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True)
        }
        
        # Add support role permissions if it exists
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True)
        
        try:
            # Create the ticket channel
            ticket_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Support ticket for {interaction.user.name} | Subject: {self.subject.value}"
            )
            
            # Store ticket info
            config["tickets"][str(ticket_id)] = {
                "creator_id": str(interaction.user.id),
                "channel_id": str(ticket_channel.id),
                "subject": self.subject.value,
                "opened_at": datetime.datetime.now().isoformat(),
                "closed": False
            }
            save_config(config)
            
            # Create ticket embed
            ticket_embed = discord.Embed(
                title=f"Ticket #{ticket_id:04d}: {self.subject.value}",
                description=self.description.value,
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            ticket_embed.add_field(name="Created by", value=interaction.user.mention)
            ticket_embed.set_footer(text="Use the buttons below to manage this ticket")
            
            # Create ticket management view
            ticket_controls = TicketControlsView(ticket_id)
            
            # Send the initial message in the ticket channel
            await ticket_channel.send(
                content=f"{interaction.user.mention}" + (f" {support_role.mention}" if support_role else ""),
                embed=ticket_embed,
                view=ticket_controls
            )
            
            # Send confirmation to user
            await interaction.response.send_message(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to create ticket channels.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred while creating your ticket: {str(e)}",
                ephemeral=True
            )

class TicketControlsView(View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id=f"close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button):
        # Confirm closure
        confirm_view = ConfirmCloseView(self.ticket_id)
        await interaction.response.send_message(
            "Are you sure you want to close this ticket? This will delete the channel in 10 seconds after closing.",
            view=confirm_view,
            ephemeral=True
        )

class ConfirmCloseView(View):
    def __init__(self, ticket_id):
        super().__init__(timeout=10)
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Yes, Close Ticket", style=discord.ButtonStyle.red, emoji="✅")
    async def confirm_close(self, interaction: discord.Interaction, button):
        # Close the ticket
        config = load_config()
        if "tickets" not in config or str(self.ticket_id) not in config["tickets"]:
            await interaction.response.send_message("This ticket no longer exists.", ephemeral=True)
            return
        
        # Mark ticket as closed
        ticket_data = config["tickets"][str(self.ticket_id)]
        ticket_data["closed"] = True
        ticket_data["closed_by"] = str(interaction.user.id)
        ticket_data["closed_at"] = datetime.datetime.now().isoformat()
        save_config(config)
        
        # Get the channel
        channel = interaction.channel
        
        # Create transcript (optional - you can expand this)
        # For a simple implementation, let's just archive by changing permissions
        try:
            # Remove user access but keep log viewable by staff
            ticket_creator_id = int(ticket_data.get("creator_id"))
            creator = interaction.guild.get_member(ticket_creator_id)
            
            if creator:
                await channel.set_permissions(creator, read_messages=False)
            
            # Send closure notice
            close_embed = discord.Embed(
                title=f"Ticket #{self.ticket_id:04d} Closed",
                description=f"This ticket has been closed by {interaction.user.mention}.\nThis channel will be deleted in 10 seconds.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            await channel.send(embed=close_embed)
            
            # Disable all buttons on the view
            for child in self.children:
                child.disabled = True
            
            await interaction.response.edit_message(content="Ticket closing...", view=self)
            
            # Schedule channel deletion
            await asyncio.sleep(10)
            await channel.delete(reason=f"Ticket #{self.ticket_id:04d} closed by {interaction.user}")
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to manage this ticket channel.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred while closing the ticket: {str(e)}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(content="Ticket closure cancelled.", view=None)

# Setup command for the ticket system
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx, channel: discord.TextChannel = None, support_role: discord.Role = None):
    """Set up a ticket system in the specified channel"""
    if not channel:
        channel = ctx.channel
    
    # Create embed for ticket system
    embed = discord.Embed(
        title="🎫 Support Tickets DataBOUNTY",
        description="Need help? Click the button below to create a support ticket.\n\n"
                   "A private channel will be created where you can discuss your issue with our support team.",
        color=discord.Color.blurple()
    )
    
    # Create button view
    view = TicketButton()
    
    # Send message with button
    message = await channel.send(embed=embed, view=view)
    
    # Store configuration
    config = load_config()
    config["ticket_system"] = {
        "channel_id": channel.id,
        "message_id": message.id
    }
    
    if support_role:
        config["support_role_id"] = support_role.id
    
    save_config(config)
    
    await ctx.send(f"Ticket system has been set up in {channel.mention}!")

# Add this to your on_ready event
@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    
    # Existing code...
    config = load_config()
    if "registration_form" in config:
        bot.add_view(RegistrationButton())
    
    # Add ticket button view
    if "ticket_system" in config:
        bot.add_view(TicketButton())
        
    # Add ticket control views for any open tickets
    if "tickets" in config:
        for ticket_id, ticket_data in config["tickets"].items():
            if not ticket_data.get("closed", False):
                bot.add_view(TicketControlsView(int(ticket_id)))


        
bot.run(TOKEN)