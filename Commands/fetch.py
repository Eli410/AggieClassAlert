from discord import app_commands
import discord
import asyncio
import sqlite3
import time
import json
import gzip
import os
from datetime import datetime


description = """
Fetch data from the data channel and store complete JSON payloads
"""


@app_commands.command(name='fetch', description=description)
async def fetch(interaction: discord.Interaction):
    if interaction.user.id != interaction.client.application.owner.id:
        await interaction.response.send_message("You are not the owner of this bot!", ephemeral=True)
        return
    
    await interaction.response.send_message("Collecting full JSON data from channel...", ephemeral=False)
    
    data_channel = interaction.client.get_channel(1354172503366303825)
    processing = True
    
    # Counters for progress tracking
    json_files_processed = 0
    db_records_saved = 0
    compressed_files_saved = 0
    total_db_size = 0
    total_compressed_size = 0
    
    async def progress_updater():
        while processing:
            try:
                await interaction.edit_original_response(
                    content=f"Processing JSON files... "
                           f"Files: {json_files_processed}, "
                           f"DB records: {db_records_saved}, "
                           f"Compressed files: {compressed_files_saved}"
                )
            except Exception:
                pass
            await asyncio.sleep(5)
    
    updater_task = asyncio.create_task(progress_updater())
    
    # ---- SQLite setup for full JSON storage ----
    try:
        conn = sqlite3.connect('dataset.db')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA temp_store=MEMORY')
        conn.execute('PRAGMA cache_size=-20000')
        
        # New table structure for complete JSON storage
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS json_snapshots (
          message_id INTEGER PRIMARY KEY,
          timestamp INTEGER NOT NULL,
          filename TEXT NOT NULL,
          json_data TEXT NOT NULL,
          json_size INTEGER NOT NULL,
          processed_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_json_snapshots_timestamp ON json_snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_json_snapshots_filename ON json_snapshots(filename);
        """)
        
        cur = conn.cursor()
        conn.execute('BEGIN')
        
    except Exception as e:
        processing = False
        try:
            updater_task.cancel()
            await updater_task
        except asyncio.CancelledError:
            pass
        await interaction.edit_original_response(content=f"Error initializing database: {e}. Aborting.")
        return
    
    # Create directory for compressed JSON files
    compressed_dir = "compressed_json_data"
    os.makedirs(compressed_dir, exist_ok=True)
    
    # Process messages from Discord channel
    async for message in data_channel.history(limit=100, oldest_first=True):
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.endswith('.json'):
                    try:
                        json_files_processed += 1
                        json_content = await attachment.read()
                        json_str = json_content.decode('utf-8')
                        
                        # Verify it's valid JSON
                        json.loads(json_str)
                        
                        ts = int(message.created_at.timestamp())
                        processed_at = int(time.time())
                        json_size = len(json_str)
                        
                        # Check if this message is already in database
                        cur.execute("SELECT message_id FROM json_snapshots WHERE message_id = ?", (message.id,))
                        if cur.fetchone() is None:
                            # Store complete JSON in database
                            cur.execute(
                                """INSERT INTO json_snapshots 
                                   (message_id, timestamp, filename, json_data, json_size, processed_at)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (message.id, ts, attachment.filename, json_str, json_size, processed_at)
                            )
                            db_records_saved += 1
                            total_db_size += json_size
                        
                        # Save to compressed JSON file
                        iso_timestamp = datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')
                        compressed_filename = f"{compressed_dir}/data_{iso_timestamp}_{message.id}.json.gz"
                        
                        if not os.path.exists(compressed_filename):
                            with gzip.open(compressed_filename, 'wt', encoding='utf-8') as f:
                                f.write(json_str)
                            
                            compressed_size = os.path.getsize(compressed_filename)
                            compressed_files_saved += 1
                            total_compressed_size += compressed_size
                        
                        print(f"Processed {attachment.filename} from {message.created_at.isoformat()}")
                        print(f"  Original size: {json_size:,} bytes")
                        if os.path.exists(compressed_filename):
                            compressed_size = os.path.getsize(compressed_filename)
                            compression_ratio = compressed_size / json_size * 100
                            print(f"  Compressed size: {compressed_size:,} bytes ({compression_ratio:.1f}% of original)")
                        
                    except Exception as e:
                        print(f"Error processing attachment {attachment.filename}: {e}")
    
    processing = False
    try:
        updater_task.cancel()
        await updater_task
    except asyncio.CancelledError:
        pass
    
    # Finalize database
    try:
        conn.commit()
        conn.execute('PRAGMA optimize')
        
        # Get final database file size
        db_file_size = os.path.getsize('dataset.db')
        
    finally:
        cur.close()
        conn.close()
    
    # Final summary with size comparisons
    summary = (
        f"✅ Ingestion complete!\n"
        f"📊 **Summary:**\n"
        f"• JSON files processed: {json_files_processed}\n"
        f"• DB records saved: {db_records_saved}\n"
        f"• Compressed files saved: {compressed_files_saved}\n\n"
        f"💾 **Size Comparison:**\n"
        f"• Total original JSON size: {total_db_size:,} bytes\n"
        f"• Total compressed size: {total_compressed_size:,} bytes\n"
        f"• Database file size: {db_file_size:,} bytes\n"
    )
    
    if total_db_size > 0:
        compression_ratio = total_compressed_size / total_db_size * 100
        summary += f"• Compression ratio: {compression_ratio:.1f}%\n"
    
    summary += f"\n📁 Compressed files saved to: `{compressed_dir}/`"
    
    await interaction.edit_original_response(content=summary)