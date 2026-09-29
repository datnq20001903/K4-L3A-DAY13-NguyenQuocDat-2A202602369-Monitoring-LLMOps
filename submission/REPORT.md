# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Quốc Đạt
- **MSSV:** 2A202602369
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/datnq20001903/K4-L3A-DAY13-NguyenQuocDat-2A202602369-Monitoring-LLMOps
- **Commit SHA source/evidence:** `8d95ec3`
- **Commit SHA nộp:** xem `git log -1 --oneline` sau commit report cuối
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602369`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytests.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Dashboard snapshot | `evidence/11-dashboard-snapshot.json` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

### CP0 baseline — 2026-09-29

- `/health`: HTTP 200, `ok: true`, `tracing_enabled: true`.
- Load test: 10 request trả HTTP 200; tạo `data/logs.jsonl` với 63 record tại thời điểm kiểm tra.
- `validate_logs.py`: 50/100; 24 record thiếu required fields, 58 record thiếu enrichment context, 14 correlation ID duy nhất, 0 PII leak.
- `validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
- `python -m pytest -q`: 18 passed, 3 failed, 4 errors. Các lỗi baseline liên quan đến quyền tạo thư mục tạm của Windows sandbox (`PermissionError`), cần chạy lại trong môi trường local đầy đủ quyền trước khi nộp.

### CP1 verification — 2026-09-29

- Đã lưu log CP0 tại `data/logs.cp0-baseline.jsonl`, khởi động lại API và tạo log sạch tại `data/logs.jsonl`.
- `validate_logs.py`: 100/100; 0 record thiếu required fields, 0 record thiếu enrichment context, 10 correlation ID duy nhất, 0 PII leak.
- Sample log chứa `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`; email/điện thoại/CCCD/thẻ được redact trước khi ghi file.

### CP2.1 trace verification — 2026-09-29

- Langfuse project đã nhận 10 trace mới từ workload `load_test.py --concurrency 5`.
- Cả 10 trace đều có cây `AGENT` → `RETRIEVER` (`retrieve-context`) và `GENERATION` (`generate-response`).
- Cả 10 root trace có user ID đã hash, session ID, feature, model, environment và correlation ID.
- Generation có model `claude-sonnet-4-5`, input/output token usage và cost; kiểm tra PII trên input/output/metadata trả về 0 match.
- Trace IDs: `81f7f321a8bd26a7841fbc706c4221c0`, `e2ec04823cdd164f86c9b0b7d976f117`, `00f745b1e88ea0ca2992104d0cd9d6bf`, `ebcc14cd0de951a1c30340759bfa608f`, `3680130ab9ced023ca5881ebbaadae7d`, `0cf52ad2598374d05048db19f4656bd6`, `80100b47335068c80e24076c1673e549`, `f51f843c09dd0924c377369720c222eb`, `41bdd0ce47ecb037965a9ec2e3ef63b3`, `a1d139d610c1ec22ef065ee56461d587`.

### CP2.2 prompt versioning verification — 2026-09-29

- Prompt `day13-chat` version 1 có labels `baseline` và `production`.
- Version 2 có label `candidate` và thêm một hướng dẫn ngắn yêu cầu dùng retrieved context, trả lời súc tích.
- Cùng một input đã chạy với `baseline` và `candidate`; trace metadata lần lượt xác nhận v1/v2 và `prompt_source=langfuse`.
- Đã promote `production` sang v2, chạy trace xác nhận v2; sau đó rollback `production` về v1 và chạy trace xác nhận v1.
- Evidence chi tiết: `evidence/15-prompt-versioning.md`.

### CP2.3 dashboard, SLO và alerts verification — 2026-09-29

- `python scripts/validate_dashboard.py`: `HỢP LỆ: 6/6 panel có trong dashboard contract.`
- Dashboard runtime có đúng 6 panel, time range 60 phút, unit và threshold/SLO line. Evidence ảnh: `evidence/11-dashboard-overview.png`.
- Snapshot baseline: latency P50/P95/P99 = `2157/2176,7/2189,66 ms`, TTFT P95 = `50 ms`; traffic = `32 request` (`0,533333 request/phút`); error rate = `0%`; retrieval success = `100%`; cost = `0,066105 USD`; tokens input/output = `1050/4197`; quality proxy mean = `0,85`.
- SLO chính giữ ở `99,5%` trong cửa sổ `28d`: request tốt là `response_sent` với `latency_ms <= 3000`. Error budget = `100 - 99,5 = 0,5%`, tương đương tối đa `5/1000 request`; snapshot hiện tại quan sát `100%`, budget consumed `0%`.
- Ba alert symptom-based đã hoàn thiện: `high_tail_latency` (warning, 5m), `retrieval_success_degraded` (warning, 5m), `request_error_rate_breach` (critical, 10m). Mỗi alert có Slack `#llmops-alerts`, owner và runbook tại `docs/alerts.md`.

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 50/100 | 100/100 | 87 record hiện tại, không thiếu field/enrichment và không có PII leak. |
| `validate_dashboard.py` | 6/6 panel | 6/6 panel | Dashboard runtime dùng cùng contract. |
| `pytest` | 18 passed, 3 failed, 4 errors | 30 passed | Full suite đã chạy trong môi trường project với quyền temp đầy đủ. |
| Số traces hợp lệ | Chưa thống kê | 10 | CP2.1 đã xác nhận span tree và metadata. |
| Số PII leak | 0 | 0 | Theo log validator. |
| Latency P95 / TTFT P95 | Chưa tính | 2176,7 ms / 50 ms | Từ dashboard snapshot 60 phút. |
| Retrieval success rate | Chưa tính | 100% | Từ `response_sent.tool_success`. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware nhận `x-request-id` hoặc sinh `req-<8-hex>`, bind vào structlog contextvars và trả lại qua `x-request-id`/`x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env` được bind trước `request_received`.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` chạy trước `JsonlFileProcessor` và JSON renderer, scrub đệ quy mọi string trong event/payload; pattern bao phủ email, điện thoại Việt Nam, CCCD và thẻ thanh toán.
- **Cách kiểm chứng kết quả:** Log CP0 được đổi tên, API restart, chạy lại load test trên log sạch; `validate_logs.py` đạt 100/100 với 0 PII leak.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Dùng workload local và Langfuse CLI truy vấn các trace mới theo thời gian tạo; CP2.1 đã xác nhận 10 trace trong project cấu hình từ `.env`.
- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` là root `AGENT`; `retrieve-context` là child `RETRIEVER`; `generate-response` là child `GENERATION` cùng parent root.
- **Cách nối trace với log:** Dùng cùng `correlation_id` trong structured log và trace metadata; ví dụ trace `a1d139d610c1ec22ef065ee56461d587` có correlation ID `req-b1d94c1e`.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** v1 — `baseline`, `production`.
- **Version/label candidate:** v2 — `candidate`.
- **Trace ID của mỗi version:** v1 baseline `73153591e95cc745eba2b5bc3182a53b`; v2 candidate `4faea91f1176204006e6d80c2c177fd2`; v2 production `2836360d2a62cbfd2c5355d9bb73a7e9`; v1 rollback `94b7483ebde165b5fb3f62fd0fd9a980`.
- **Cách promote và rollback `production`:** Dùng Langfuse SDK `update_prompt`; promote v2 bằng labels `candidate, production`, sau đó gán lại `production` cho v1 bằng labels `baseline, production`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/dashboard_snapshot.py` đọc `data/logs.jsonl`, lọc 60 phút và tạo runtime dashboard. Evidence ảnh `evidence/11-dashboard-overview.png` có đủ latency P50/P95/P99 + TTFT P95, traffic, error rate/breakdown/retrieval success, cost, input/output tokens và quality proxy; mỗi panel hiển thị unit và threshold từ `config/dashboard.yaml`.
- **SLO và lý do chọn:** `fast_successful_requests` đạt 99,5% trong 28 ngày khi request có `response_sent` và `latency_ms <= 3000`. Ngưỡng 3 giây phản ánh giới hạn chờ người dùng và đồng nhất với latency threshold của dashboard.
- **Cách tính error budget:** `100% - 99,5% = 0,5%`; tức tối đa 5 request không đạt trên mỗi 1.000 request. Snapshot hiện tại có observed SLI 100% và budget consumed 0%.
- **Ba alert và runbook tương ứng:** `high_tail_latency` → `docs/alerts.md#alert-1`; `retrieval_success_degraded` → `docs/alerts.md#alert-2`; `request_error_rate_breach` → `docs/alerts.md#alert-3`. Tất cả có duration, severity, owner và Slack `#llmops-alerts`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`; incident `rag_slow`.
- **Khoảng thời gian điều tra:** `2026-09-29T04:33:26.276238Z` → `2026-09-29T05:33:26.276238Z`; challenge load bắt đầu lúc `2026-09-29T05:33:00.845832Z`.
- **Triệu chứng từ metrics:** P95 latency `4661 ms` và P99 `4664.2 ms`, vượt threshold `3000 ms`; SLO giảm còn `86.486486%`. TTFT P95 vẫn `50 ms`, error rate `0%`, retrieval success `100%`.
- **Log line và correlation ID liên quan:** log `response_sent` lúc `2026-09-29T05:33:07.625174Z`, `latency_ms=4666`, `tool_name=retrieval`, `tool_success=true`, correlation ID `req-4d3b96f0`; xem `evidence/13-incident-log.png`.
- **Trace ID và span gây ảnh hưởng:** trace `787d722d9012bec4cc9cde4e2ceabcc9`; `retrieve-context` kéo dài `2501 ms` trong root `4668 ms`, còn `generate-response` chỉ `152 ms`; xem `evidence/14-incident-trace.png`.
- **Root cause:** incident `rag_slow` làm bước retrieval chậm; trace xác nhận retrieval là span chiếm phần lớn thời gian, không phải generation hay lỗi tool.
- **Fix action:** tắt scenario `rag_slow`, áp dụng timeout/fallback cho retrieval và kiểm tra lại P95 bằng cùng challenge workload.
- **Preventive measure:** giữ alert P95 > 3000 ms, alert retrieval success, correlation ID end-to-end và dashboard Metrics → Logs → Traces; bổ sung test/span budget để phát hiện retrieval vượt ngân sách trước khi ảnh hưởng người dùng.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng processor scrub PII đệ quy trước JSON renderer/file writer và đồng thời truyền `correlation_id` qua structlog, log và trace; cách này bảo vệ dữ liệu ngay trước điểm lưu trữ và giữ được khả năng điều tra end-to-end.
- **Một lỗi/blocker đã gặp:** Windows sandbox chặn thư mục temp khiến pytest báo lỗi giả; lần truy vấn trace cũ cũng trả API 410 vì endpoint legacy không còn dùng cho organization mới.
- **Cách tìm nguyên nhân và xử lý:** Chạy lại pytest bằng `.venv` với quyền filesystem đầy đủ để đạt 30/30; chuyển truy vấn Langfuse sang Observations API v2, rồi dùng `correlation_id` và timestamp để xác nhận trace.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết P95 tăng trong khoảng nào; log lọc request bất thường và cung cấp correlation ID; trace mở đúng request để so sánh duration/status từng span và xác định root cause.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version giúp so sánh và rollback có kiểm soát; token/cost cho biết tác động tài chính; SLO/error budget biến latency thành ngưỡng vận hành; rollback production giảm rủi ro khi candidate không đạt.
- **Điều quan trọng nhất đã học:** HTTP 200 không đủ chứng minh hệ thống khỏe; phải nối tín hiệu định lượng, request cụ thể và span cụ thể trước khi kết luận.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Một số validator evidence được lưu dưới dạng PNG terminal; các ảnh incident 12–14 được render trực tiếp từ log runtime và Langfuse Observations API v2, có source/ID rõ ràng và không chứa secret hoặc PII thô.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối. *(Cập nhật SHA sau commit CP4.)*
- [x] Tất cả output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
