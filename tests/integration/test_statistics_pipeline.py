"""
M1.4.5 — Statistics Pipeline Validation

验证完整数据链:
    Usage Data → CostCalculator → Repository → Statistics → Dashboard Data Model

使用固定测试数据:
    model = gpt-4o-mini
    prompt_tokens = 1000
    completion_tokens = 500
    价格: input=$0.15/1M, output=$0.60/1M

预期 Cost:
    input_cost  = 1000 × 0.15/1000000 = 0.00015
    output_cost =  500 × 0.60/1000000 = 0.00030
    total_cost  = 0.00045

运行:
    python tests/integration/test_statistics_pipeline.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Ensure project root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.database.manager import DatabaseManager
from src.database.repository import Repository
from src.parser.base import UsageData
from src.statistics.calculator import CostCalculator
from src.statistics.engine import StatisticsEngine


# ── Fixed test data ──────────────────────────────────────────────
MODEL_NAME = "gpt-4o-mini"
PROVIDER = "openai"
INPUT_TOKENS = 1000
OUTPUT_TOKENS = 500
TOTAL_TOKENS = INPUT_TOKENS + OUTPUT_TOKENS  # 1500

# gpt-4o-mini pricing (per 1M tokens)
INPUT_PRICE_PER_1M = 0.15   # $0.15/1M
OUTPUT_PRICE_PER_1M = 0.60  # $0.60/1M

# Expected cost
EXPECTED_INPUT_COST = INPUT_TOKENS * INPUT_PRICE_PER_1M / 1_000_000   # 0.00015
EXPECTED_OUTPUT_COST = OUTPUT_TOKENS * OUTPUT_PRICE_PER_1M / 1_000_000  # 0.00030
EXPECTED_TOTAL_COST = round(EXPECTED_INPUT_COST + EXPECTED_OUTPUT_COST, 8)  # 0.00045


def setup_test_db() -> tuple[DatabaseManager, Repository, str]:
    """创建临时 SQLite 数据库并初始化 Schema。

    Returns:
        (DatabaseManager, Repository, db_path)
    """
    # 使用临时文件避免污染生产数据库
    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_stats_")
    os.close(fd)

    db = DatabaseManager(db_path)
    db.initialize_schema()

    # 插入 gpt-4o-mini 定价
    repo = Repository(db)
    repo.insert_model({
        "provider": PROVIDER,
        "model_name": MODEL_NAME,
        "display_name": "GPT-4o Mini",
        "input_price": INPUT_PRICE_PER_1M,
        "output_price": OUTPUT_PRICE_PER_1M,
        "currency": "USD",
        "enabled": 1,
    })

    return db, repo, db_path


def cleanup_test_db(db: DatabaseManager, db_path: str) -> None:
    """清理临时数据库。"""
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_cost_calculation(calculator: CostCalculator) -> dict:
    """测试 1: CostCalculator 计算正确性。

    Args:
        calculator: 已初始化的 CostCalculator（含 gpt-4o-mini 定价）。

    Returns:
        测试结果。
    """
    print("\n" + "-" * 50)
    print("  Test 1: Cost Calculation")
    print("-" * 50)

    result = calculator.calculate(
        model=MODEL_NAME,
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
    )

    print(f"  Input:  {INPUT_TOKENS} tokens × ${INPUT_PRICE_PER_1M}/1M")
    print(f"          = ${result.input_cost:.8f}")
    print(f"  Output: {OUTPUT_TOKENS} tokens × ${OUTPUT_PRICE_PER_1M}/1M")
    print(f"          = ${result.output_cost:.8f}")
    print(f"  Total:  ${result.total_cost:.8f}")
    print(f"  Currency: {result.currency}")

    checks = {
        "input_cost": result.input_cost == EXPECTED_INPUT_COST,
        "output_cost": result.output_cost == EXPECTED_OUTPUT_COST,
        "total_cost": result.total_cost == EXPECTED_TOTAL_COST,
        "currency_usd": result.currency == "USD",
    }

    for name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")
        if not passed:
            if name == "input_cost":
                print(f"    Expected: {EXPECTED_INPUT_COST}, Got: {result.input_cost}")
            elif name == "output_cost":
                print(f"    Expected: {EXPECTED_OUTPUT_COST}, Got: {result.output_cost}")
            elif name == "total_cost":
                print(f"    Expected: {EXPECTED_TOTAL_COST}, Got: {result.total_cost}")

    return checks


def test_repository_write(repository: Repository, calculator: CostCalculator) -> dict:
    """测试 2: Repository 写入正确性。

    Args:
        repository: Repository 实例。
        calculator: CostCalculator 实例。

    Returns:
        测试结果。
    """
    print("\n" + "-" * 50)
    print("  Test 2: Repository Write")
    print("-" * 50)

    # 构建 UsageData（含 Provider Identity）
    usage = UsageData(
        provider=PROVIDER,
        model=MODEL_NAME,
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
        total_tokens=TOTAL_TOKENS,
        latency_ms=123.45,
        endpoint="https://api.openai.com/v1/chat/completions",
        status_code=200,
        client_type="openai",
        actual_provider="openai",
        pricing_version="2026-06-openai",
        usage_source="api",
    )

    # 计算费用
    cost = calculator.calculate(
        model=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )

    # 写入 request_logs
    log_entry = usage.to_dict()
    log_entry["cost"] = cost.total_cost
    log_entry["currency"] = cost.currency
    log_id = repository.insert_request_log(log_entry)
    print(f"  Inserted request_log: id={log_id}")

    # 写入 daily_stats
    from datetime import date
    today = date.today().isoformat()
    repository.upsert_daily_stats({
        "date": today,
        "provider": usage.provider,
        "model": usage.model,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "request_count": 1,
        "cost": cost.total_cost,
        "currency": cost.currency,
    })
    print(f"  Upserted daily_stats: date={today}")

    # 验证 request_logs 读回
    recent = repository.get_recent_requests(limit=1)
    checks = {}
    if recent:
        row = recent[0]
        print(f"  Read back request_log: provider={row['provider']}, model={row['model']}, "
              f"tokens={row['total_tokens']}, cost={row['cost']}")
        checks["log_provider"] = row["provider"] == PROVIDER
        checks["log_model"] = row["model"] == MODEL_NAME
        checks["log_input_tokens"] = row["input_tokens"] == INPUT_TOKENS
        checks["log_output_tokens"] = row["output_tokens"] == OUTPUT_TOKENS
        checks["log_total_tokens"] = row["total_tokens"] == TOTAL_TOKENS
        checks["log_cost"] = abs(row["cost"] - EXPECTED_TOTAL_COST) < 0.000001
        checks["log_currency"] = row["currency"] == "USD"
        checks["log_client_type"] = row.get("client_type", "") == "openai"
        checks["log_actual_provider"] = row.get("actual_provider", "") == "openai"
        checks["log_pricing_version"] = row.get("pricing_version", "") == "2026-06-openai"
        checks["log_usage_source"] = row.get("usage_source", "") == "api"
    else:
        checks["log_exists"] = False
        print("  ✗ No request_log found!")

    # 验证 daily_stats 读回
    today_rows = repository.get_daily_stats(today)
    if today_rows:
        row = today_rows[0]
        print(f"  Read back daily_stats: date={row['date']}, model={row['model']}, "
              f"tokens={row['total_tokens']}, requests={row['request_count']}, "
              f"cost={row['cost']}")
        checks["stats_date"] = row["date"] == today
        checks["stats_model"] = row["model"] == MODEL_NAME
        checks["stats_total_tokens"] = row["total_tokens"] == TOTAL_TOKENS
        checks["stats_request_count"] = row["request_count"] == 1
        checks["stats_cost"] = abs(row["cost"] - EXPECTED_TOTAL_COST) < 0.000001
    else:
        checks["stats_exists"] = False
        print("  ✗ No daily_stats found!")

    for name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")

    return checks


def test_statistics_aggregation(repository: Repository, calculator: CostCalculator) -> dict:
    """测试 3: Statistics Engine 聚合正确性。

    Args:
        repository: Repository 实例。
        calculator: CostCalculator 实例。

    Returns:
        测试结果。
    """
    print("\n" + "-" * 50)
    print("  Test 3: Statistics Aggregation")
    print("-" * 50)

    engine = StatisticsEngine(repository, calculator)

    # 使用 engine.record() 写入第二条数据（同一 model，不同 token 数量）
    usage2 = UsageData(
        provider=PROVIDER,
        model=MODEL_NAME,
        input_tokens=2000,
        output_tokens=800,
        total_tokens=2800,
        client_type="openai",
        actual_provider="openai",
        pricing_version="2026-06-openai",
        usage_source="api",
    )

    # record() 会: 计算费用 → 写入 request_logs → 更新 daily_stats → 返回 summary
    summary = engine.record(usage2)
    print(f"  Recorded usage via engine: tokens={usage2.total_tokens}")

    # 验证 summary
    expected_today_tokens = TOTAL_TOKENS + 2800  # 1500 + 2800 = 4300
    expected_today_input = INPUT_TOKENS + 2000   # 1000 + 2000 = 3000
    expected_today_output = OUTPUT_TOKENS + 800  # 500 + 800 = 1300

    # 第二条数据的费用
    cost2 = calculator.calculate(model=MODEL_NAME, input_tokens=2000, output_tokens=800)
    expected_today_cost = round(EXPECTED_TOTAL_COST + cost2.total_cost, 8)

    print(f"  Summary:")
    print(f"    today_tokens:  {summary.today_tokens} (expected: {expected_today_tokens})")
    print(f"    today_input:   {summary.today_input_tokens} (expected: {expected_today_input})")
    print(f"    today_output:  {summary.today_output_tokens} (expected: {expected_today_output})")
    print(f"    today_requests: {summary.today_requests} (expected: 2)")
    print(f"    today_cost:    ${summary.today_cost} (expected: ${round(expected_today_cost, 4)})")
    print(f"    active_models: {summary.active_models}")
    print(f"    top_models:    {summary.top_models}")

    checks = {
        "summary_today_tokens": summary.today_tokens == expected_today_tokens,
        "summary_today_input": summary.today_input_tokens == expected_today_input,
        "summary_today_output": summary.today_output_tokens == expected_today_output,
        "summary_today_requests": summary.today_requests == 2,
        "summary_today_cost": abs(summary.today_cost - round(expected_today_cost, 4)) < 0.0001,
        "summary_active_models": MODEL_NAME in summary.active_models,
        "summary_top_models_nonempty": len(summary.top_models) > 0,
        "summary_has_last_request": summary.last_request_time is not None,
    }

    for name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {name}")

    return checks


def test_dashboard_data_model(repository: Repository) -> dict:
    """测试 4: Dashboard 数据模型查询。

    验证 UI 层常用的查询方法返回正确的数据结构。

    Args:
        repository: Repository 实例。

    Returns:
        测试结果。
    """
    print("\n" + "-" * 50)
    print("  Test 4: Dashboard Data Model")
    print("-" * 50)

    from datetime import date

    today = date.today().isoformat()
    checks = {}

    # 1. get_daily_stats — Dashboard 主数据
    stats = repository.get_daily_stats(today)
    assert stats, "No daily_stats found"
    row = stats[0]
    required_fields = ["date", "provider", "model", "input_tokens",
                       "output_tokens", "total_tokens", "request_count", "cost", "currency"]
    missing_fields = [f for f in required_fields if f not in row]
    checks["daily_stats_fields"] = len(missing_fields) == 0
    if missing_fields:
        print(f"  ✗ daily_stats missing fields: {missing_fields}")
    else:
        print(f"  ✓ daily_stats has all {len(required_fields)} required fields")

    # 2. get_top_models_for_date — Dashboard Top Models
    top = repository.get_top_models_for_date(today, limit=5)
    checks["top_models_nonempty"] = len(top) > 0
    print(f"  {'✓' if top else '✗'} get_top_models_for_date: {len(top)} results")
    if top:
        tm = top[0]
        top_fields = ["model", "provider", "total_tokens", "cost"]
        missing_top_fields = [f for f in top_fields if f not in tm]
        checks["top_models_fields"] = len(missing_top_fields) == 0
        if missing_top_fields:
            print(f"    ✗ top_models missing fields: {missing_top_fields}")
        else:
            print(f"    ✓ top_models has all {len(top_fields)} required fields")
        # 验证聚合值
        checks["top_models_aggregated"] = tm["total_tokens"] == 4300  # 1500 + 2800
        print(f"    {'✓' if checks['top_models_aggregated'] else '✗'} "
              f"aggregated tokens: {tm['total_tokens']} (expected: 4300)")

    # 3. get_recent_requests — History 页面数据
    recent = repository.get_recent_requests(limit=10)
    checks["recent_nonempty"] = len(recent) >= 2
    print(f"  {'✓' if checks['recent_nonempty'] else '✗'} get_recent_requests: {len(recent)} >= 2")
    if recent:
        rq = recent[0]
        rq_fields = ["id", "timestamp", "provider", "model", "input_tokens",
                      "output_tokens", "total_tokens", "cost", "currency"]
        missing_rq_fields = [f for f in rq_fields if f not in rq]
        checks["recent_fields"] = len(missing_rq_fields) == 0

    # 4. get_total_tokens_for_date — 浮窗显示
    total_tokens_today = repository.get_total_tokens_for_date(today)
    checks["total_tokens_today"] = total_tokens_today == 4300
    print(f"  {'✓' if checks['total_tokens_today'] else '✗'} "
          f"get_total_tokens_for_date: {total_tokens_today} (expected: 4300)")

    # 5. get_total_cost_for_date — 浮窗显示
    total_cost_today = repository.get_total_cost_for_date(today)
    expected_total = EXPECTED_TOTAL_COST + (2000 * INPUT_PRICE_PER_1M / 1_000_000) + (800 * OUTPUT_PRICE_PER_1M / 1_000_000)
    checks["total_cost_today"] = abs(total_cost_today - expected_total) < 0.00001
    print(f"  {'✓' if checks['total_cost_today'] else '✗'} "
          f"get_total_cost_for_date: ${total_cost_today}")

    # 6. get_active_models_today
    active = repository.get_active_models_today()
    checks["active_models"] = MODEL_NAME in active
    print(f"  {'✓' if checks['active_models'] else '✗'} "
          f"get_active_models_today: {active}")

    for name, passed in checks.items():
        if name not in ["daily_stats_fields", "top_models_nonempty", "top_models_fields",
                         "top_models_aggregated", "recent_nonempty", "recent_fields",
                         "total_tokens_today", "total_cost_today", "active_models"]:
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")

    return checks


def main() -> int:
    """运行完整的 Statistics Pipeline 验证。"""
    print("=" * 60)
    print("  M1.4.5 — Statistics Pipeline Validation")
    print("=" * 60)
    print(f"  Model: {MODEL_NAME}")
    print(f"  Test data: prompt_tokens={INPUT_TOKENS}, completion_tokens={OUTPUT_TOKENS}")
    print(f"  Pricing: input=${INPUT_PRICE_PER_1M}/1M, output=${OUTPUT_PRICE_PER_1M}/1M")
    print(f"  Expected cost: ${EXPECTED_TOTAL_COST}")

    db_path = None
    try:
        # Setup
        db, repo, db_path = setup_test_db()
        calculator = CostCalculator(repo)
        calculator.refresh()  # 刷新价格缓存

        # 验证模型定价已加载
        assert MODEL_NAME in calculator.known_models, \
            f"Model {MODEL_NAME} not in price cache: {calculator.known_models}"
        print(f"\n  Price cache loaded: {calculator.known_models}")

        all_checks: dict[str, bool] = {}

        # Test 1: Cost Calculation
        checks = test_cost_calculation(calculator)
        all_checks.update(checks)

        # Test 2: Repository Write
        checks = test_repository_write(repo, calculator)
        all_checks.update(checks)

        # Test 3: Statistics Aggregation
        checks = test_statistics_aggregation(repo, calculator)
        all_checks.update(checks)

        # Test 4: Dashboard Data Model
        checks = test_dashboard_data_model(repo)
        all_checks.update(checks)

        # Report
        print("\n" + "=" * 60)
        print("  Test Results Summary")
        print("=" * 60)

        passed = sum(1 for v in all_checks.values() if v)
        total = len(all_checks)
        failed = total - passed

        for name, result in all_checks.items():
            status = "✓" if result else "✗"
            if not result:
                print(f"  {status} {name}  ← FAILED")

        print(f"\n  {passed}/{total} checks passed, {failed} failed")

        if failed == 0:
            print("\n  ✅ Statistics Pipeline — ALL CHECKS PASSED")
            print("\n  Pipeline verified:")
            print("    Usage Data → CostCalculator → Repository → Statistics → Dashboard Data")
            return 0
        else:
            print(f"\n  ❌ Statistics Pipeline — {failed} CHECKS FAILED")
            return 1

    except Exception as e:
        print(f"\n  ❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if db_path:
            cleanup_test_db(db, db_path)


if __name__ == "__main__":
    sys.exit(main())
