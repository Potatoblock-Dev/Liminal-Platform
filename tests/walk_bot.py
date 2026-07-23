"""本地联机冒烟辅助：一个来回走动并偶尔跳跃的机器人客户端。"""

import asyncio
import json
import sys

from websockets.asyncio.client import connect


async def main(duration_s: float = 30.0) -> None:
    url = "ws://127.0.0.1:8103/avatar-lobby/ws?dev_user=bot&dev_name=Bot"
    async with connect(url) as ws:
        await ws.send(json.dumps({"type": "join", "protocolVersion": 5, "roomId": "public"}))

        async def drain() -> None:
            try:
                while True:
                    await ws.recv()
            except Exception:
                pass

        drain_task = asyncio.create_task(drain())
        sequence = 0
        direction = 1
        steps = int(duration_s / 0.05)
        for i in range(steps):
            if i % 60 == 59:
                direction = -direction
            await ws.send(
                json.dumps(
                    {
                        "type": "input",
                        "protocolVersion": 5,
                        "sequence": sequence,
                        "direction": direction,
                        "jump": i % 80 == 40,
                        "kneel": False,
                    }
                )
            )
            sequence += 1
            await asyncio.sleep(0.05)
        drain_task.cancel()


if __name__ == "__main__":
    asyncio.run(main(float(sys.argv[1]) if len(sys.argv) > 1 else 30.0))
