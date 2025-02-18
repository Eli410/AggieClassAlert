from api import get_section_details
import json
import asyncio


async def main():
    res = await get_section_details(202511, '12354')
    with open('class_list.json', 'w') as f:
        json.dump(res, f, indent=4)


if __name__ == '__main__':
    asyncio.run(main())