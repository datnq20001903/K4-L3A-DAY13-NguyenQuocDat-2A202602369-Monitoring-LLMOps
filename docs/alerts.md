# Alert và runbook — Day 13

Các alert dưới đây là symptom-based: điều kiện dùng tín hiệu người dùng hoặc
SLO trong dashboard, không phụ thuộc tên hàm hay implementation nội bộ. Tất cả
được gửi tới Slack `#llmops-alerts`, owner trực ca là `on-call-llmops`.

## Alert 1

- Tên: `high_tail_latency`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: latency SLO `fast_successful_requests`, ngưỡng 3.000 ms.
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000` liên tục 5 phút trong cửa sổ 60 phút.
- Ảnh hưởng tới người dùng: phần đuôi request chậm, người dùng phải chờ lâu hoặc timeout ở client.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency, đối chiếu P50/P95/P99 với TTFT để xác định chậm ở toàn request hay ngay lúc bắt đầu sinh.
  2. Lọc log `response_sent` có `latency_ms > 3000`, lấy `correlation_id` và kiểm tra phân bố theo `tool_name`.
  3. Mở trace theo correlation ID, so sánh duration của `retrieve-context` và `generate-response`.
- Mitigation tạm thời: giảm concurrency của load/traffic không cần thiết, bật timeout/fallback retrieval và chuyển prompt/model về cấu hình production ổn định nếu trace cho thấy generation chậm.
- Owner: `on-call-llmops`

## Alert 2

- Tên: `retrieval_success_degraded`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: guardrail retrieval success tối thiểu 90%.
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90` liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu context, giảm độ tin cậy hoặc phải fallback sang câu trả lời chung.
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors: retrieval success và breakdown lỗi theo `error_type`/`tool_name`.
  2. Lọc các response có `tool_success: false`, lấy correlation ID và xác nhận request tương ứng.
  3. Mở trace, kiểm tra duration, status và metadata của observation `retrieve-context`.
- Mitigation tạm thời: chuyển sang index/nguồn retrieval dự phòng, tăng timeout có kiểm soát và giữ câu trả lời fallback không lộ dữ liệu nhạy cảm.
- Owner: `on-call-llmops`

## Alert 3

- Tên: `request_error_rate_breach`
- Severity: `critical`
- Duration: `10m`
- Kênh thông báo: Slack `#llmops-alerts`
- SLI/SLO liên quan: error-rate guardrail tối đa 2% và error budget của SLO 99,5%.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` liên tục 10 phút.
- Ảnh hưởng tới người dùng: nhiều request thất bại hoặc không nhận được câu trả lời; có nguy cơ đốt error budget nhanh.
- Ba bước kiểm tra đầu tiên:
  1. Xác định thời điểm bắt đầu từ panel Errors và breakdown theo `error_type`.
  2. Lấy ít nhất một correlation ID từ log `request_failed`, kiểm tra header và response tương ứng.
  3. Mở trace request đó, tìm observation lỗi đầu tiên và đối chiếu latency, retrieval, generation với SLO.
- Mitigation tạm thời: rollback prompt/model hoặc release gần nhất, bật fallback response, giới hạn traffic và thông báo incident channel nếu error rate tiếp tục tăng.
- Owner: `on-call-llmops`
