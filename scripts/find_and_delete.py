import asyncio, httpx

headers = {
    'X-API-Key': 'sk_crywlilpru72vge7jeayhljmgvcc3fm2wnvzvsshujrf7n7va3cq',
    'X-Shalom-Email': 'alexandra.calero0202@gmail.com',
    'X-Shalom-Password': 'Alexandra020203!',
    'Content-Type': 'application/json'
}

target_guia = '105301975'

async def check(client, oid):
    try:
        r = await client.get(f'https://api.shalom-api-peru.com/v1/orders/{oid}', headers=headers)
        if r.status_code == 200:
            data = r.json()
            g = data.get('guia') or data.get('numero')
            if str(g) == target_guia:
                print(f'*** ENCONTRADO! ose_id: {oid} para guia {g} ***')
                # Delete it!
                r_del = await client.delete(f'https://api.shalom-api-peru.com/v1/orders/{oid}', headers=headers)
                print('DELETE STATUS:', r_del.status_code, r_del.text)
                return True
    except:
        pass
    return False

async def main():
    async with httpx.AsyncClient(timeout=5.0, limits=httpx.Limits(max_connections=30)) as client:
        start = 108772942 + 400
        # Let's search around start in batches of 50
        for b_start in range(108772942, 108774000, 50):
            tasks = [check(client, oid) for oid in range(b_start, b_start + 50)]
            results = await asyncio.gather(*tasks)
            if any(results):
                break
            print(f'Scanned up to {b_start+50}...')

asyncio.run(main())
