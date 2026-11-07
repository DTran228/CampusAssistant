# Bàn giao ngày 7 tháng 11 năm 2026

Luồng hiện tại là chọn workshop trong A, duyệt phần muốn nhớ, đóng A, mở B trên cùng profile và kiểm tra lại thời gian từ nguồn mới. SQLite lưu dữ liệu; MCP cung cấp giao diện đọc/lưu cho các trợ lý. Các milestone tháng 10 vẫn là lịch sử của nền tảng trước đó.

## Tự chạy lại hai MCP client độc lập trên Windows

```powershell
Set-Location C:\dev\CampusAssistant
.\.venv\Scripts\python.exe -m eval.handoff_demo
```

A hiển thị summary, sở thích `robotics, workshop`, tên/giờ và event ID/revision. Đọc rồi nhập `yes`. Đây là dữ liệu demo; không nhập lịch hoặc thông tin cá nhân thật vào ví dụ này. Sau khi lưu, SDK client và MCP server của A thoát hoàn toàn. Script cập nhật nguồn fixture rồi mở B bằng một SDK session và server subprocess mới trên cùng database/profile. B gọi `get_planning_context {}`; không nhận mã plan truyền từ A.

Workshop **build a rover** ban đầu ở **thứ Tư 28/10, 16:00–17:00 EDT**. Nguồn mới chuyển sang **thứ Ba 27/10, 14:15–15:15 EDT**, trùng lớp **14:00–15:30** trong `classes.ics`. Stable event ID giữ nguyên, source revision tăng 1 → 2. `revalidate_plan` trả giờ trước/sau, `source_changed`, `schedule_conflict` và giải thích. Summary cũ không được coi là thời gian hiện tại đáng tin cậy.

Sinh viên có thể giữ lựa chọn cũ để xem lại hoặc chọn **sensors lab**, thứ Năm 29/10, 16:00–17:00 EDT. Export lựa chọn cũ bị chặn. Script còn thử hủy workshop, profile khác, ghi bằng revision cũ, lưu lỗi và xóa context. Nó yêu cầu `yes` lần thứ hai trước khi lưu phương án thay thế thành plan mới rồi xuất ICS. Plan ban đầu vẫn còn.

`--approve-fixture` thay các câu trả lời bằng xác nhận giả lập để chạy tự động. Đây là kiểm thử phần mềm, không phải quan sát người dùng thật. Các database demo nằm trong thư mục tạm riêng và được dọn khi kết thúc; kết quả không chứa profile capability được ghi vào `eval/results/handoff.json`.

## Tự đổi giờ trong giao diện web

```powershell
$env:CAMPUS_DATA_DIR='C:\dev\CampusAssistant\runtime\handoff-demo'
$env:CAMPUS_NOW='2026-10-26T12:00:00-04:00'
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-handoff
.\.venv\Scripts\python.exe -m campus_assistant.cli serve
```

Mở `http://127.0.0.1:5555`. Trong **My availability**, upload `data/demo/classes.ics`, từ 26/10 đến 2/11, timezone `America/New_York`. Trong **Explore events**, chọn cùng khoảng ngày, lịch vừa upload, sở thích `robotics, workshop`, giá tối đa 0. Chọn **build a rover**, lưu plan. Trong **My plan**, điền summary, kiểm tra sở thích, tên/giờ và phiên bản sự kiện, tick xác nhận rồi bấm **Save approved context**.

Trong terminal thứ hai, đặt đúng hai biến môi trường trên rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m campus_assistant.cli demo-change --workshop
```

Refresh **My plan** hoặc để B gọi `revalidate_plan` sau khi lấy context. Giờ mới trùng lớp, export bị chặn; phương án khác chỉ là gợi ý. Muốn đổi, quay lại Explore, chọn sự kiện rồi lưu/share plan mới. **Clear shared context** xóa nội dung chia sẻ nhưng giữ plan và lịch. Client đang giữ revision cũ phải tải lại và xin duyệt trước khi ghi tiếp.

Để web và hai host MCP có chung dữ liệu, pairing **một lần** qua My availability rồi `cli pair`; cấu hình cả A/B bằng cùng `CAMPUS_DATA_DIR` và private `CAMPUS_PROFILE`, theo [MCP_SETUP.md](MCP_SETUP.md). Không cần copy plan ID giữa các lần dùng. Một profile mới tạo bằng `cli profile` là danh tính khác nên thấy context trống. Profile là quyền truy cập cục bộ: người có quyền đọc database/config trên máy vẫn ở cùng ranh giới tin cậy hệ điều hành.

Đồng hồ demo cố ý ở tháng 10 để giữ fixture tái hiện được; đây không phải ngày thực của buổi kiểm thử. Chạy `demo-handoff` lại khôi phục nội dung nguồn nhưng giữ lịch sử revision và plan. Dùng thư mục data mới nếu muốn thấy đúng revision 1 → 2.

## Kiểm thử phần mềm và nghiên cứu người dùng

Baseline trước sửa: **69 offline test đạt, 1 real-retrieval test không chạy**. Các lỗi ban đầu do sandbox chặn temp/socket đã được phân biệt với lỗi phần mềm. Sau triển khai, test đếm cố định một migration được cập nhật để kiểm tra toàn bộ migration hiện có; database đã có plan cũng được thử nâng cấp.

Lệnh kiểm tra cuối cùng:

Toàn bộ suite offline đạt **75 test**, 1 real-retrieval test deselected. Kiểm tra web riêng sau lần chỉnh cách hiển thị cuối cùng đạt **3/3**. `pip check`, compileall, Node syntax và Git whitespace đều đạt. Demo independent-client và evaluation đều thành công; planner có **36 ca**, **0** incorrect feasible recommendations và **0** missed valid options.

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m 'not real_retrieval' --basetemp=tmp/handoff-final-check --junitxml=eval/results/handoff-tests.xml
.\.venv\Scripts\python.exe -m eval.handoff_demo --approve-fixture
.\.venv\Scripts\python.exe -m eval.run
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q campus_assistant eval tests
node --check static/js/script1.js
git diff --check
```

Kết quả hiện tại nằm ở `handoff-verification.json`, `handoff-tests.xml`, `handoff.json` và `offline.json` trong `eval/results`. MCP demo dùng **official SDK client/subprocess**, chưa thử một desktop host cụ thể. Kiểm tra browser thực đã lưu context qua form và xem lại sau reload; ảnh tại `docs/screenshots/handoff-context.png`. HTTP tests kiểm tra review/save/clear, CSRF, pairing và session khác. Kiểm tra MPNet/FAISS thật vẫn là bước riêng, chưa chạy lại trong đợt này; file kết quả tháng 10 là bằng chứng lịch sử.

Evaluation có 36 fixture planner và 40 câu hỏi lexical demo, không phải dữ liệu thực của trường. Không có người tham gia nghiên cứu (**0**); thời gian hoàn thành tác vụ, tỷ lệ hoàn thành và mức giảm thời gian thực đều **chưa đo**. Mốc giảm **30%** chỉ là mục tiêu nghiên cứu. Muốn công bố cần tuyển sinh viên có đồng thuận, đối chứng manual browsing, đảo thứ tự điều kiện, cùng điểm kết thúc là lựa chọn cuối đã lưu/kiểm tra không xung đột, và báo cả thất bại. Xem `STUDY_PROTOCOL.md`; không thay bằng sinh viên mô phỏng.

Trước khi phát triển tiếp, cần hiểu bốn điểm: SQLite giữ context sau khi client thoát; MCP để client khác đọc qua contract; profile giới hạn dữ liệu được đọc/ghi; stable event reference cho phép lấy revision mới thay vì tin vào summary đã cũ. Không cần thêm dịch vụ hay framework để hoàn thành luồng cục bộ này.
