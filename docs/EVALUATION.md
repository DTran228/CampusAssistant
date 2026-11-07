# Evaluation and limits

Chạy `python -m eval.run`. Không cần API key/model. Kết quả raw trong `eval/results/offline.json`: base commit, dirty state, implementation/dataset SHA256, timestamp UTC, Python/OS/CPU, fixed clock và từng record. Hash không gồm chính result để tránh tự tham chiếu. Vì thay đổi chưa commit, base commit **không** tự đại diện toàn bộ implementation; dùng fingerprint đi kèm.

## Correctness

36 fixture planner cố ý gồm valid lẫn invalid: overlap nhiều dạng, adjacency, buffer ranh giới, cancel, budget known/unknown, food tri-state, deadline, date bounds, already-started, offset normalization và all-day busy. Mỗi fixture chạy qua database, calendar upload và hàm recommend thật. Báo cả incorrect feasible recommendation lẫn missed valid option và số ca valid, tránh kết quả đẹp do không trả gì. Test bổ sung kiểm tra RRULE/EXDATE/moved/cancelled instances, DST, export race, source errors, private ownership và protocol.

Đây là bộ test hữu hạn. Zero lỗi trên fixture không đồng nghĩa độ tin cậy 100% trong dữ liệu thế giới thực. Các dạng ICS không hỗ trợ bị từ chối rõ ràng.

## Retrieval

40 câu: mỗi nguồn có 6 answerable, 2 ambiguous, 2 unanswerable. Split theo **source/topic**, không random từng câu: career/library là development, registrar/services là held-out. Passage literal và page cho phép con người review. Không sửa ngưỡng theo kết quả held-out.

Recall@3 trung bình trên answerable: phần passage/page chuẩn được tìm thấy; không tính ambiguous/unanswerable vào denominator. Report riêng unanswerable abstention (không excerpt). Raw ambiguous outputs được lưu để review, không gọi chúng là đã giải quyết. Demo lexical chạy trên 8 chunk rất nhỏ; không được dùng số này làm semantic retrieval benchmark hay generalization claim. Có false positive ở unanswerable: excerpt không chứng minh câu hỏi đã có đáp án.

`python -m eval.smoke_retrieval` dùng model MPNet/FAISS thật, lưu `real-retrieval-smoke.json`, tách khỏi offline. Cần cài `.[retrieval]` và tải model công khai. Smoke 3 query chỉ kiểm tra đường model/index/page evidence, không thay thế bộ đánh giá quality. Nếu model/download lỗi, status unavailable và exit code 2; không giả vờ pass.

Generation mặc định disabled. Citation existence chỉ là cú pháp; chưa có độc lập factual-support review. Chưa báo tỷ lệ unsupported-answer cho model chưa chạy. Muốn đánh giá LLM: giữ nguyên câu hỏi/split, lưu câu trả lời và evidence, nhờ người độc lập gán supported/unsupported/unclear theo từng claim; báo lỗi và abstention riêng.

## Performance

Workload cố định: 8 chunk, 6 events, recurring class calendar; 50 warm sample, một first-call sample, raw latency retrieval/planning/total. First call của benchmark **không** phải cold process/OS (corpus vừa được ingest/evaluate); ghi rõ cache OS không kiểm soát. Real-model load/index latency thuộc smoke riêng. Generation không đo. Median là quan sát local tiny-corpus, không là SLA; không claim p95 ổn định, không so sánh với baseline chưa benchmark.

## User impact

Chưa có participant; impact, time saved, satisfaction và success rate thực đều **chưa đo**. Xem `STUDY_PROTOCOL.md`, `study_tasks.json`, `study_records_template.csv`. Raw study records tương lai phải de-identify và lưu `eval/private/` (gitignored). Không dùng simulated users thay cho sinh viên thật.
