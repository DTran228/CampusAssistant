# Architecture and decisions / Các quyết định cần hiểu

Một ứng dụng Python, SQLite, Jinja và JavaScript thuần. Không có frontend build, hàng đợi hay dịch vụ phụ. Hai giao diện web/MCP gọi cùng `documents`, `events`, `calendars`, `planner`.

## Vì sao Python quyết định lịch?

LLM có thể viết câu trả lời nhưng không đáng tin để tính overlap, DST hay revision. Python áp dụng bộ lọc cứng trước: khoảng ngày, trạng thái active, deadline, giá được biết, free food được xác nhận, và lịch bận. Sau đó xếp hạng theo số interest khớp chuỗi, thời gian, ID. Có tối đa năm đề xuất; đây là các lựa chọn riêng lẻ, không phải lịch trình tối ưu. Khi lưu/xuất nhiều sự kiện, kiểm tra lại xung đột giữa chúng.

Khoảng lịch là `[start,end)`. Hai sự kiện liền nhau không chồng lấn; buffer thêm khoảng đệm ở ranh giới một lần, không nhân đôi. Đây không phải phép tính quãng đường đi bộ. Chưa biết giá không đạt free-only. `free_food`/`dietary` có ba trạng thái; không suy luận an toàn ăn uống.

## SQLite và revision

`migrations/001_initial.sql` chứa schema; `schema_migrations` đánh dấu file đã áp dụng. Bật foreign keys trên mỗi connection. Query giá trị dùng tham số SQL. `BEGIN IMMEDIATE` lấy quyền ghi trước khi kiểm tra và xuất để source refresh khác không chen giữa bước kiểm tra revision và tạo ICS. Export phản ánh snapshot tại thời điểm đó; nguồn vẫn có thể thay đổi sau khi tải file.

Event identity là `(source_id,source_event_id)`, không theo title. Cùng nội dung không tăng revision; retrieval time vẫn cập nhật. Nội dung đổi/hủy thêm `event_revisions`; feed lỗi giữ dữ liệu cũ. Record lỗi được báo riêng, nguồn partial không được coi là fresh để export. Disappearance không có nghĩa cancellation.

Plan giữ revision đã chọn và query/constraint gốc. Page refresh hoặc MCP revalidation so sánh với nguồn hiện tại, chỉ ra field đổi, hủy, conflict, source freshness, và đề xuất thay thế không xung đột với phần selection còn hợp lệ. Không tự sửa lựa chọn. Xem lại chi tiết ở Explore và lưu selection mới để xác nhận revision mới. Xóa availability khiến plan cần review, không tự coi toàn bộ thời gian là trống.

## Ngữ cảnh giữa hai trợ lý

Migration `002_planning_context.sql` bổ sung một ngữ cảnh hiện tại cho mỗi profile; không sửa dữ liệu plan/calendar cũ. Chỉ lưu summary ngắn, danh sách sở thích đã duyệt, plan reference, revision và thời điểm cập nhật. Các event ID/revision lấy qua `plan_items`, không nhân bản thành bộ nhớ hội thoại. `planning_context.py` gọi `planner.store_plan` trong cùng `BEGIN IMMEDIATE` để validate rồi lưu plan mới và context nguyên tử. Plan có sẵn phải thuộc profile; cả lúc đọc lại cũng kiểm tra ownership.

Client gửi `expected_revision` và `reviewed:true` sau khi hiển thị trường thực tế cho sinh viên. Nếu revision đã đổi, trả `stale_context`; không tự retry để tránh mất sửa đổi từ trợ lý khác. Server không thể kiểm chứng người thật đã bấm xác nhận trong host. Xóa context làm rỗng nội dung nhưng giữ số phiên bản; client cũ không thể tái tạo dữ liệu bằng revision trước khi xóa. Trigger khi xóa plan cũng xóa nội dung context liên kết. Xóa context không xóa plan/calendar và không thu hồi bản sao đã tới host.

SQLite giữ ngữ cảnh khi A thoát; MCP cho B đọc qua contract; profile xác định dữ liệu được phép đọc; event reference ổn định giúp planner đối chiếu revision nguồn mới. Summary có thể cũ: B phải gọi `revalidate_plan`, xem giờ trước/sau và giải thích xung đột trước khi sinh viên quyết định. Không cần cache chung giữa các client, dịch vụ mới hay database khác.

## Tài liệu và index

PDF do quản trị viên chỉ định qua CLI, tối đa 20 MiB/500 trang; dùng pypdf, không OCR. Chunk baseline 500 ký tự, overlap 150. Stable chunk ID phụ thuộc source/page/offset/hash. Mỗi rebuild tạo file JSON và FAISS bất biến riêng; SQLite chỉ chuyển active revision khi hoàn tất cả hai. JSON được kiểm tra lại với metadata SQLite trước khi tìm kiếm. Build thất bại giữ active index trước đó; có thể còn orphan artifact do lỗi giữa lúc ghi file và commit, dọn thủ công trong workspace demo khi không dùng.

Default `demo` là lexical fixture backend, không phải embedding mô phỏng được quảng cáo như model thật. `mpnet` dùng all-mpnet-base-v2 + FAISS IndexFlatL2, vector normalize; similarity = `1 - distance/2`. Ngưỡng 0.30 là heuristic ban đầu, không phải độ tin cậy chính sách. Không đọc bất cứ pickle cũ/upload nào. Index command thay toàn bộ corpus; manifest đầy đủ dùng cho nhiều tài liệu. Reindex tường minh, không theo dõi file tự động.

Optional llama.cpp được nạp lần đầu cần dùng, cache một model/process và lock khi generation. Citation IDs phải tồn tại, nhưng điều đó không chứng minh câu trả lời được hỗ trợ. Kết quả luôn ghi `unverified_generated_answer`; lỗi generation vẫn trả excerpt. Search chỉ cung cấp evidence và chỉ dẫn xác nhận với văn phòng, không quyết định điều kiện di trú/pháp lý. Nguồn mâu thuẫn/cũ phải được văn phòng chịu trách nhiệm xác nhận; ứng dụng không phân xử chúng.

## ICS: hỗ trợ có giới hạn

UTC, IANA TZID, floating times có timezone được chọn, all-day với exclusive DTEND, daily/weekly/monthly/yearly RRULE, EXDATE, moved/cancelled RECURRENCE-ID. Horizon tối đa 30 ngày, tối đa 2,000 occurrence, 10,000 bước expansion. Anchor recurrence quá 10 năm bị từ chối. Giữ wall time của lớp qua DST; local time không tồn tại bị từ chối ở sự kiện gốc, bỏ occurrence RRULE không tồn tại theo RFC. Giờ nhập nhằng ở DST fallback yêu cầu export expanded UTC.

RDATE, EXRULE, SECONDLY/HOURLY/MINUTELY, RANGE=THISANDFUTURE, custom TZID không có trong IANA và METHOD request/cancel delta không được hỗ trợ. Trả `calendar_unsupported`, không im lặng coi là rảnh. Feed yêu cầu snapshot METHOD absent/PUBLISH; cancellation qua STATUS trong snapshot. Chỉ lưu interval, timezone/horizon và opaque reference; bỏ raw bytes/titles.

## Ranh giới dữ liệu riêng

Web dùng cookie session opaque 256-bit, HttpOnly/SameSite=Strict; server map sang profile. CSRF token trên mọi thay đổi; Origin/Host được kiểm tra, CSP và textContent tránh HTML injection, không CORS toàn cục. Các tham chiếu calendar/plan luôn giới hạn profile. Không nhận user ID/path từ MCP tool.

MCP process bắt buộc profile do CLI tạo hoặc pairing. Pairing một lần, TTL 10 phút, token chỉ lưu hash; UI nói rõ chia sẻ dữ liệu session với local MCP. Profile là capability cục bộ, không phải tài khoản đăng nhập. Bất cứ người có quyền đọc SQLite hoặc config profile đều ở cùng trust boundary hệ điều hành. Không public host. Chưa có account recovery, session expiry tự động, at-rest encryption hay cơ chế auth cho nhiều tenant.

Source fetch chỉ được cấu hình qua CLI. Mỗi request/redirect kiểm tra đúng host, http(s), không URL credentials; DNS address phải global (trừ exemption loopback fixture). Socket pin IP đã kiểm tra, TLS xác minh hostname. Tối đa ba redirect, 1 MiB và socket timeout 5 giây với deadline tổng khoảng 15 giây; DNS resolution phụ thuộc giới hạn resolver của OS. Không log calendar body.

## Chủ động làm mới

Refresh nguồn là CLI action. Plan check chỉ chạy khi yêu cầu/refresh trang. Không scheduler, push notification hay lời hứa realtime. Campus timezone/name cấu hình bằng biến môi trường; không tự nhận diện trường hoặc nguồn thật.
