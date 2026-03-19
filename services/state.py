import asyncio

devhouse_lock = asyncio.Lock()
devhouse_queue = asyncio.Queue()
uat_approval_event = asyncio.Event()
uat_decision = {"approved": False}
