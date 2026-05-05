#!/usr/bin/env python3
"""
ChatTutor 并发压力测试脚本

测试场景：
- 多用户并发访问 /api/v1/chat 接口
- 观察响应时间、错误率、限流触发情况

使用方法：
    python scripts/concurrency_test.py --base-url http://localhost:8000 --users 5 --requests 20
"""

import asyncio
import aiohttp
import argparse
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime


@dataclass
class TestResult:
    user_id: str
    request_num: int
    status_code: int
    response_time_ms: float
    error: str = ""
    body: dict = field(default_factory=dict)


@dataclass
class TestReport:
    total_requests: int = 0
    successful: int = 0
    rate_limited: int = 0
    failed: int = 0
    response_times: List[float] = field(default_factory=list)
    results_by_user: Dict[str, List[TestResult]] = field(default_factory=dict)

    def add_result(self, result: TestResult):
        self.total_requests += 1
        self.response_times.append(result.response_time_ms)

        if result.user_id not in self.results_by_user:
            self.results_by_user[result.user_id] = []
        self.results_by_user[result.user_id].append(result)

        if result.status_code == 200:
            self.successful += 1
        elif result.status_code == 429:
            self.rate_limited += 1
        else:
            self.failed += 1

    def print_summary(self):
        print("\n" + "=" * 60)
        print("并发压力测试报告")
        print("=" * 60)
        print(f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总请求数：{self.total_requests}")
        print(f"成功请求：{self.successful} ({self.successful/self.total_requests*100:.1f}%)")
        print(f"被限流：  {self.rate_limited} ({self.rate_limited/self.total_requests*100:.1f}%)")
        print(f"失败：    {self.failed} ({self.failed/self.total_requests*100:.1f}%)")

        if self.response_times:
            print(f"\n响应时间统计:")
            print(f"  平均：{statistics.mean(self.response_times):.0f} ms")
            print(f"  中位数：{statistics.median(self.response_times):.0f} ms")
            print(f"  P95:   {statistics.quantiles(self.response_times, n=100)[94]:.0f} ms")
            print(f"  最大：  {max(self.response_times):.0f} ms")
            print(f"  最小：  {min(self.response_times):.0f} ms")

        print("\n每用户统计:")
        for user_id, results in sorted(self.results_by_user.items()):
            user_success = sum(1 for r in results if r.status_code == 200)
            user_limited = sum(1 for r in results if r.status_code == 429)
            user_avg = statistics.mean([r.response_time_ms for r in results])
            print(f"  {user_id}: 成功={user_success}, 限流={user_limited}, 平均响应={user_avg:.0f}ms")

        print("=" * 60)


async def register_user(session: aiohttp.ClientSession, base_url: str, username: str, password: str) -> str:
    """注册用户并返回 token"""
    try:
        # 先尝试注册
        async with session.post(
            f"{base_url}/api/v1/auth/register",
            json={"username": username, "password": password}
        ) as resp:
            # 409 表示用户已存在，可以忽略
            if resp.status not in [200, 409]:
                print(f"注册失败：{username}, status={resp.status}")

        # 登录获取 token
        async with session.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": username, "password": password}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("access_token")
            else:
                print(f"登录失败：{username}, status={resp.status}")
                return None
    except Exception as e:
        print(f"用户 {username} 认证异常：{e}")
        return None


async def send_chat_request(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    user_id: str,
    request_num: int,
    message: str
) -> TestResult:
    """发送单个聊天请求"""
    start = time.perf_counter()
    try:
        async with session.post(
            f"{base_url}/api/v1/chat",
            json={"message": message, "task_id": f"test_{user_id}"},
            headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            elapsed = (time.perf_counter() - start) * 1000
            body = await resp.json() if resp.status == 200 else {}
            return TestResult(
                user_id=user_id,
                request_num=request_num,
                status_code=resp.status,
                response_time_ms=elapsed,
                body=body
            )
    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        return TestResult(
            user_id=user_id,
            request_num=request_num,
            status_code=0,
            response_time_ms=elapsed,
            error=str(e)
        )


async def run_concurrency_test(
    base_url: str,
    num_users: int,
    requests_per_user: int,
    delay_between_requests: float = 0.1
):
    """运行并发测试"""
    print(f"\n开始并发测试:")
    print(f"  基础 URL: {base_url}")
    print(f"  用户数：{num_users}")
    print(f"  每用户请求数：{requests_per_user}")
    print(f"  总请求数：{num_users * requests_per_user}")
    print(f"  请求间隔：{delay_between_requests}s")

    # 健康检查
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{base_url}/health") as resp:
                if resp.status != 200:
                    print(f"⚠️  健康检查失败：{resp.status}")
                else:
                    print("✓ 健康检查通过")
        except Exception as e:
            print(f"⚠️  无法连接服务器：{e}")
            return

    # 注册/登录所有用户
    print(f"\n正在获取 {num_users} 个用户的 token...")
    tokens: Dict[str, str] = {}

    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(num_users):
            username = f"testuser_{i}"
            password = "test123"
            tasks.append(register_user(session, base_url, username, password))

        results = await asyncio.gather(*tasks)
        for i, token in enumerate(results):
            if token:
                tokens[f"testuser_{i}"] = token
                print(f"  ✓ user_{i} token 获取成功")
            else:
                print(f"  ✗ user_{i} token 获取失败")

    if len(tokens) == 0:
        print("无法获取任何用户 token，请检查服务是否正常运行")
        return

    # 并发发送请求
    print(f"\n开始发送 {num_users * requests_per_user} 个请求...")
    report = TestReport()

    start_time = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        tasks = []
        for user_id, token in tokens.items():
            for req_num in range(requests_per_user):
                message = f"并发测试请求 #{req_num + 1} from {user_id}"
                task = send_chat_request(
                    session, base_url, token, user_id, req_num + 1, message
                )
                tasks.append(task)

                # 如果设置了延迟，添加异步延迟
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)

        results = await asyncio.gather(*tasks)

        for result in results:
            report.add_result(result)
            if result.status_code == 429:
                print(f"  [限流] {result.user_id} 请求 #{result.request_num}")
            elif result.status_code != 200:
                print(f"  [失败] {result.user_id} 请求 #{result.request_num}: {result.error or result.status_code}")

    elapsed = time.perf_counter() - start_time

    print(f"\n测试完成，耗时：{elapsed:.2f}s")
    print(f"吞吐量：{report.total_requests / elapsed:.1f} 请求/秒")

    report.print_summary()

    # 保存详细结果
    output_file = f"concurrency_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    import json
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": report.total_requests,
                "successful": report.successful,
                "rate_limited": report.rate_limited,
                "failed": report.failed,
                "duration_seconds": elapsed,
                "throughput": report.total_requests / elapsed,
            },
            "response_times": report.response_times,
            "per_user": {
                user_id: [
                    {"request": r.request_num, "status": r.status_code, "time_ms": r.response_time_ms}
                    for r in results
                ]
                for user_id, results in report.results_by_user.items()
            }
        }, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已保存：{output_file}")


def main():
    parser = argparse.ArgumentParser(description="ChatTutor 并发压力测试")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="API 基础 URL (默认：http://localhost:8000)")
    parser.add_argument("--users", type=int, default=5,
                        help="并发用户数 (默认：5)")
    parser.add_argument("--requests", type=int, default=20,
                        help="每个用户的请求数 (默认：20)")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="请求间隔秒数 (默认：0.1)")

    args = parser.parse_args()

    asyncio.run(run_concurrency_test(
        base_url=args.base_url,
        num_users=args.users,
        requests_per_user=args.requests,
        delay_between_requests=args.delay
    ))


if __name__ == "__main__":
    main()
