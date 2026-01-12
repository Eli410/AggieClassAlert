import asyncio
from api import HOWDY_API

async def main():
    details = await HOWDY_API.get_syllabus('202611', '27369')
    with open('syllabus.pdf', 'wb') as f:
        f.write(details)

if __name__ == "__main__":
    asyncio.run(main())
