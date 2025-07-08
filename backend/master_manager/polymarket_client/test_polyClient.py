from .polymarket_client import create_polymarket_client, PolymarketClient
import json
import asyncio

'''
TokenIds - Isreal x Hamas Ceasefire

clobTokenIds":"[\"36983600554365577850917051019051094208107094324057250177743040919797354737778\", 

\"27328614281599691408249679475598101144024812037645322360848849289647283526760\"]"


'''


async def main():
    clobTokenIds = "[\"36983600554365577850917051019051094208107094324057250177743040919797354737778\", \"27328614281599691408249679475598101144024812037645322360848849289647283526760\"]"

    poly_client: PolymarketClient = create_polymarket_client(slug="israel-x-hamas-ceasefire-by-july-15", token_ids=json.loads(clobTokenIds))
    await poly_client.connect()
    #isSubscribed = await poly_client.subscribe()
    await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())


