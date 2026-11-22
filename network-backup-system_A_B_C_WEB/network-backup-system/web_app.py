"""Streamlit Web UI cho Network Backup System A+B+C. Chạy: streamlit run web_app.py"""
from dataclasses import asdict
from pathlib import Path
import json

import streamlit as st
import yaml
from dotenv import load_dotenv

from app.logging_setup import setup_logging
from app.runner import safe_data
from app.web_backend import ROOT, WebController, clean_table, launch_scheduler

load_dotenv(ROOT / '.env')
setup_logging()
st.set_page_config(page_title='Network Backup Manager', page_icon='🖧', layout='wide')

st.markdown('''<style>
.block-container{padding-top:1.7rem;max-width:1450px}
[data-testid="stMetric"]{border:1px solid #ccd5df55;border-radius:12px;padding:14px}
</style>''', unsafe_allow_html=True)


def controller():
    return WebController(workers=int(st.session_state.get('workers', 4)))


def call(fn, *, success=None):
    try:
        value = fn()
        if success:
            st.success(success)
        return value
    except Exception as exc:
        # Không đưa raw SSH response hoặc dữ liệu bí mật ra web.
        st.error(f'Tác vụ không thành công ({type(exc).__name__}). Kiểm tra dữ liệu và logs/operations.log.')
        return None


def mutate(fn, success):
    try:
        fn()
        st.success(success)
        st.rerun()
    except Exception as exc:
        st.error(f'Không thực hiện được ({type(exc).__name__}). Kiểm tra dữ liệu và logs/operations.log.')


def results_table(results):
    st.session_state['last_results'] = results
    st.dataframe(clean_table(results), use_container_width=True, hide_index=True)
    st.caption('Thất bại trên một thiết bị không làm dừng các thiết bị khác. Kết quả không chứa mật khẩu hoặc raw SSH output.')


def choose_devices(items, key):
    return st.multiselect('Chọn thiết bị', [x.name for x in items], key=key)


def yaml_dict(text, label):
    try:
        value = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f'{label} không phải YAML hợp lệ.') from exc
    if not isinstance(value, dict):
        raise ValueError(f'{label} phải có dạng mapping YAML.')
    return value


def device_fields(prefix, initial=None):
    d = asdict(initial) if initial else {}
    a, b, c = st.columns(3)
    with a:
        name = st.text_input('Tên', value=d.get('name', ''), key=prefix+'name')
        host = st.text_input('IPv4/IPv6', value=d.get('host', ''), key=prefix+'host')
        port = st.number_input('SSH port', min_value=1, max_value=65535,
                               value=int(d.get('port', 22)), key=prefix+'port')
    with b:
        platform = st.selectbox('Nền tảng', ['cisco_ios', 'mikrotik_routeros'],
                                index=['cisco_ios', 'mikrotik_routeros'].index(d.get('platform', 'cisco_ios')),
                                key=prefix+'platform')
        group = st.text_input('Nhóm', value=d.get('group', 'lab'), key=prefix+'group')
        role = st.selectbox('Vai trò', ['router', 'switch'],
                            index=['router', 'switch'].index(d.get('role', 'router')) if d.get('role', 'router') in ('router', 'switch') else 0,
                            key=prefix+'role')
    with c:
        tags = st.text_input('Tags (cách nhau dấu phẩy)', value=', '.join(d.get('tags', [])), key=prefix+'tags')
        cred = st.text_input('Credential profile', value=d.get('credential_profile', 'LAB'), key=prefix+'cred')
    return dict(name=name.strip(), host=host.strip(), port=int(port), platform=platform,
                group=group.strip(), role=role, tags=[x.strip() for x in tags.split(',') if x.strip()],
                credential_profile=cred.strip())


st.title('🖧 Network Backup Manager')
st.caption('Giao diện Web sử dụng nguyên các module A (thiết bị/inventory), B (backup, restore, scheduler) và C (runner, template, báo cáo).')
with st.sidebar:
    st.header('Thiết lập')
    st.slider('Luồng SSH tối đa', 1, 12, 4, key='workers')
    st.info('Chỉ sử dụng trong mạng lab tin cậy. Mặc định truy cập từ máy này (localhost).')
    st.caption(f'Dự án: {ROOT.name}')
    if st.button('Làm mới dữ liệu', use_container_width=True):
        st.rerun()

ctrl = call(controller)
if ctrl is None:
    st.stop()
infos = call(ctrl.devices)
if infos is None:
    st.stop()

s1, s2, s3 = st.columns(3)
s1.metric('Thiết bị trong Inventory', len(infos))
s2.metric('Nền tảng', len({x.platform for x in infos}))
s3.metric('Backup đã ghi', sum(len(ctrl.backups.list_backups(x.name)) for x in infos))
st.caption('Các số trên phản ánh dữ liệu local; không phải trạng thái Online. Bấm “Thu thập” để kiểm tra SSH thật.')

(t_inventory, t_collect, t_backup, t_versions, t_config, t_scheduler, t_reports) = st.tabs([
    '📋 Inventory', '🌐 Thiết bị & SSH', '💾 Backup & Kiểm tra',
    '🕘 Phiên bản & Restore', '🧩 Template & Apply', '⏱ Lịch sao lưu', '📊 Báo cáo & Log'
])

with t_inventory:
    st.subheader('Danh sách thiết bị')
    f1, f2, f3 = st.columns(3)
    with f1: group_filter = st.text_input('Lọc nhóm', key='filter_group')
    with f2: role_filter = st.text_input('Lọc vai trò', key='filter_role')
    with f3: tag_filter = st.text_input('Lọc tag', key='filter_tag')
    shown = [x for x in infos if (not group_filter or x.group == group_filter)
             and (not role_filter or x.role == role_filter)
             and (not tag_filter or tag_filter in x.tags)]
    st.dataframe([asdict(x) for x in shown], use_container_width=True, hide_index=True)
    with st.expander('➕ Thêm thiết bị'):
        with st.form('add_device'):
            fields = device_fields('new_')
            if st.form_submit_button('Thêm thiết bị'):
                mutate(lambda: ctrl.add_device(fields), 'Đã thêm thiết bị.')
    with st.expander('✏️ Sửa thiết bị'):
        if infos:
            edit_name = st.selectbox('Thiết bị cần sửa', [x.name for x in infos], key='edit_pick')
            with st.form('edit_device'):
                fields = device_fields('edit_'+edit_name+'_', next(x for x in infos if x.name == edit_name))
                if st.form_submit_button('Lưu thay đổi'):
                    mutate(lambda: ctrl.update_device(edit_name, fields), 'Đã lưu thay đổi.')
    with st.expander('🗑️ Xóa thiết bị'):
        if infos:
            delete_name = st.selectbox('Chọn thiết bị', [x.name for x in infos], key='delete_pick')
            ack = st.checkbox('Tôi xác nhận xóa thiết bị khỏi inventory (không xóa cấu hình trên thiết bị).')
            if st.button('Xóa khỏi inventory', disabled=not ack):
                mutate(lambda: ctrl.delete_device(delete_name), 'Đã xóa khỏi inventory.')

with t_collect:
    st.subheader('Thu thập thông tin và kiểm tra SSH')
    names = choose_devices(infos, 'facts_names')
    if st.button('Kết nối và thu thập', type='primary', disabled=not names):
        with st.spinner('Đang kết nối SSH tới các thiết bị được chọn...'):
            results = call(lambda: ctrl.run_task(names, 'facts'))
        if results is not None:
            results_table(results)
    st.info('Thiết bị Online chỉ được xác nhận qua kết quả SSH; không suy ra từ inventory.')

with t_backup:
    st.subheader('Sao lưu và kiểm tra thay đổi so với Baseline')
    names = choose_devices(infos, 'backup_names')
    a, b = st.columns(2)
    with a:
        if st.button('💾 Sao lưu ngay', disabled=not names, use_container_width=True):
            with st.spinner('Đang sao lưu...'):
                results = call(lambda: ctrl.run_task(names, 'backup'))
            if results is not None: results_table(results)
    with b:
        if st.button('🔎 Kiểm tra thay đổi', disabled=not names, use_container_width=True):
            with st.spinner('Đang so sánh với baseline...'):
                results = call(lambda: ctrl.run_task(names, 'check'))
            if results is not None: results_table(results)
    st.caption('Lệnh backup/check dùng đúng BackupService của B và TaskRunner của C.')

with t_versions:
    st.subheader('Quản lý phiên bản và khôi phục')
    if not infos:
        st.info('Chưa có thiết bị trong Inventory.')
    else:
        name = st.selectbox('Thiết bị', [x.name for x in infos], key='history_device')
        records = call(lambda: ctrl.history(name)) or []
        st.dataframe([asdict(x) for x in records], hide_index=True, use_container_width=True)
        record_ids = [x.backup_id for x in records]
        if record_ids:
            with st.expander('So sánh hai phiên bản', expanded=True):
                x, y = st.columns(2)
                with x: first = st.selectbox('Phiên bản thứ nhất', record_ids, key='diff_first')
                with y: second = st.selectbox('Phiên bản thứ hai', record_ids, index=min(1, len(record_ids)-1), key='diff_second')
                if st.button('Xem Diff'):
                    diff = call(lambda: ctrl.diff(first, second))
                    if diff is not None:
                        st.code(diff or '(Hai phiên bản không có khác biệt)', language='diff')
            with st.expander('Đặt Baseline'):
                baseline_id = st.selectbox('Bản chuẩn', record_ids, key='baseline_id')
                if st.button('Chọn làm Baseline'):
                    call(lambda: ctrl.baseline(name, baseline_id), success='Đã đặt Baseline.')
            with st.expander('⚠️ Khôi phục cấu hình (thao tác thực trên thiết bị)'):
                restore_id = st.selectbox('Phiên bản cần khôi phục', record_ids, key='restore_id')
                checks_text = st.text_area('Điều kiện xác minh (YAML)',
                    value='interfaces:\n  FastEthernet1/0:\n    status: up\n    protocol: up\n',
                    key='restore_checks', height=120)
                confirm = st.checkbox(f'Tôi xác nhận khôi phục {name} từ bản #{restore_id}; thiết bị sẽ thay đổi.', key='restore_confirm')
                if st.button('Khôi phục cấu hình', disabled=not confirm, type='primary'):
                    def execute_restore():
                        checks = yaml_dict(checks_text, 'Checks')
                        return ctrl.restore(name, restore_id, checks)
                    with st.spinner('Đang khôi phục và xác minh...'):
                        results = call(execute_restore)
                    if results is not None: results_table(results)
                st.warning('Khôi phục có thể gián đoạn SSH. Chỉ chạy trên lab và có cách truy cập dự phòng.')
        else:
            st.info('Chưa có bản sao. Vào tab Backup để tạo phiên bản đầu tiên.')

with t_config:
    st.subheader('Sinh cấu hình bằng Jinja2 — Dry-run — Apply — Rollback')
    names = choose_devices(infos, 'config_names')
    templates = sorted(p.name for p in (ROOT / 'templates').glob('*.j2'))
    template = st.selectbox('Template', templates) if templates else None
    default_vars = (ROOT / 'config/variables.example.yaml').read_text(encoding='utf-8')
    vars_text = st.text_area('Variables YAML', default_vars, height=140)
    checks_text = st.text_area('Checks YAML (bắt buộc cho Apply)',
        (ROOT / 'config/checks.example.yaml').read_text(encoding='utf-8'), height=140)
    if st.button('👁️ Dry-run (không kết nối SSH)', disabled=not names or not template):
        def do_preview():
            variables = yaml_dict(vars_text, 'Variables')
            return ctrl.preview(names, template, variables)
        preview = call(do_preview)
        if preview is not None:
            config_text, checks = preview
            st.session_state['preview'] = (list(names), template, vars_text, config_text, checks)
            st.dataframe(checks, use_container_width=True)
            st.code(config_text, language='text')
            st.warning('Dry-run chỉ kiểm tra cú pháp cơ bản; chưa xác minh lệnh trên thiết bị.')
    st.divider()
    st.warning('Apply thay đổi cấu hình thực. Hệ thống sao lưu trước khi áp và thử rollback một lần nếu lỗi; không khẳng định rollback thành công khi chưa xác minh.')
    confirm_apply = st.checkbox('Tôi hiểu rủi ro và xác nhận áp cấu hình lên các thiết bị đã chọn.', key='apply_confirm')
    if st.button('🚀 Apply cấu hình', type='primary', disabled=not names or not template or not confirm_apply):
        def do_apply():
            variables = yaml_dict(vars_text, 'Variables')
            checks = yaml_dict(checks_text, 'Checks')
            return ctrl.apply(names, template, variables, checks)
        with st.spinner('Đang sao lưu trước thao tác, apply và xác minh...'):
            results = call(do_apply)
        if results is not None: results_table(results)

with t_scheduler:
    st.subheader('Lịch sao lưu định kỳ')
    schedule_path = ROOT / 'config/schedule.example.yaml'
    st.code(schedule_path.read_text(encoding='utf-8'), language='yaml')
    st.caption('Sửa trực tiếp config/schedule.example.yaml trước khi khởi động lịch. Lịch chỉ chạy khi tiến trình Web còn hoạt động.')
    schedule_job = st.session_state.get('schedule_job')
    is_running = bool(schedule_job and schedule_job['thread'].is_alive())
    st.write('Trạng thái:', '**Đang chạy**' if is_running else '**Đã dừng**')
    a, b = st.columns(2)
    with a:
        if st.button('▶️ Bắt đầu scheduler', disabled=is_running, use_container_width=True):
            scheduler = call(lambda: ctrl.schedule(schedule_path))
            if scheduler is not None:
                st.session_state['schedule_job'] = {'scheduler': scheduler,
                                                     'thread': launch_scheduler(scheduler)}
                st.success('Đã khởi động lịch trong phiên Web này.')
                st.rerun()
    with b:
        if st.button('⏹ Dừng scheduler', disabled=not is_running, use_container_width=True):
            schedule_job['scheduler'].stop()
            st.info('Đã yêu cầu dừng; tác vụ SSH đang chạy sẽ được hoàn tất.')
            st.rerun()
    st.info('Có thể dùng CLI `python main.py scheduler` để chạy lịch riêng, ổn định hơn khi đóng trình duyệt.')

with t_reports:
    st.subheader('Xuất báo cáo kết quả tác vụ')
    results = st.session_state.get('last_results', [])
    if results:
        st.dataframe(clean_table(results), use_container_width=True, hide_index=True)
        a, b = st.columns(2)
        for col, fmt in ((a, 'json'), (b, 'csv')):
            with col:
                if st.button(f'Tạo file {fmt.upper()} trong reports/', key='report_'+fmt):
                    path = call(lambda f=fmt: ctrl.report(results, f))
                    if path is not None:
                        st.session_state['report_'+fmt] = path
                path = st.session_state.get('report_'+fmt)
                if path and Path(path).is_file():
                    st.download_button('Tải báo cáo '+fmt.upper(), Path(path).read_bytes(),
                        file_name=Path(path).name, mime='application/json' if fmt == 'json' else 'text/csv', key='download_'+fmt)
    else:
        st.info('Hãy chạy tác vụ SSH tại các tab trước để có dữ liệu báo cáo.')
    st.divider()
    st.subheader('Log thao tác')
    log = ROOT / 'logs/operations.log'
    if log.is_file():
        # Chỉ xem dòng cuối, không cho đọc file bất kỳ từ UI.
        st.code('\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-120:]), language='text')
    else:
        st.info('Chưa có log. Log sẽ được ghi khi thực hiện tác vụ.')
