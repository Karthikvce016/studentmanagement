/* ── Student Management System — Shared JS Utilities ── */

const API = '';

// ── Auth helpers ──────────────────────────────────────

function getToken() { return localStorage.getItem('token'); }
function getRole() { return localStorage.getItem('role'); }

function authHeaders() {
    return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() };
}

/**
 * XSS-safe HTML escaping (#1).
 * Always use esc() when injecting dynamic data into innerHTML.
 */
function esc(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

/**
 * Fetch wrapper with auth headers, error handling (#11), and auto-logout on 401.
 */
async function api(url, options = {}) {
    options.headers = { ...authHeaders(), ...options.headers };
    try {
        const res = await fetch(API + url, options);
        if (res.status === 401) { logout(); return null; }
        if (res.status >= 500) {
            console.error(`Server error ${res.status} on ${url}`);
            showAlert('alert', 'Server error — please try again later.', 'error');
            return null;
        }
        return res;
    } catch (err) {
        console.error('Network error:', err);
        showAlert('alert', 'Network error — check your connection.', 'error');
        return null;
    }
}

function logout() {
    localStorage.clear();
    window.location.href = '/';
}

function requireAuth(role) {
    if (!getToken() || getRole() !== role) {
        window.location.href = '/';
    }
}

// ── UI helpers ────────────────────────────────────────

function showAlert(id, message, type = 'success') {
    const el = document.getElementById(id);
    if (!el) return;
    el.className = `alert alert-${type} show`;
    el.textContent = message;
    setTimeout(() => el.classList.remove('show'), 4000);
}

async function openModal(id, opts = {}) {
    document.getElementById(id).classList.add('active');
    if (id === 'assignModal') {
        const [tRes, cRes] = await Promise.all([api('/admin/teachers'), api('/admin/courses')]);
        if (tRes && cRes) {
            const teachers = await tRes.json();
            const courses = await cRes.json();

            if (opts.preTeacherId) {
                // Pre-select and lock the teacher
                const tSel = document.getElementById('a_teacher');
                tSel.style.display = 'none';
                let locked = document.getElementById('a_teacher_locked');
                if (!locked) {
                    locked = document.createElement('div');
                    locked.id = 'a_teacher_locked';
                    locked.className = 'ss-input';
                    locked.style.background = '#f1f5f9';
                    locked.style.cursor = 'default';
                    tSel.parentNode.insertBefore(locked, tSel.nextSibling);
                }
                locked.textContent = `[${opts.preTeacherId}] ${opts.teacherName}`;
                locked.style.display = '';
                tSel.value = opts.preTeacherId;
                // Destroy any SearchSelect cache for this so it doesn't interfere
                if (SearchSelect._cache['a_teacher']) {
                    SearchSelect._cache['a_teacher'].input.style.display = 'none';
                }
            } else {
                // Normal: show searchable dropdown
                const locked = document.getElementById('a_teacher_locked');
                if (locked) locked.style.display = 'none';
                SearchSelect.populate('a_teacher',
                    teachers.map(t => ({ value: t.id, label: `${t.first_name} ${t.last_name}`, sub: `${t.department || 'No Dept'}` }))
                );
            }

            SearchSelect.populate('a_course',
                courses.map(c => ({ value: c.id, label: `${c.code} — ${c.name}`, sub: `${c.credits} credits` }))
            );
        }
    }
    if (id === 'enrollModal') {
        const [sRes, cRes] = await Promise.all([api('/admin/students'), api('/admin/courses')]);
        if (sRes && cRes) {
            const students = await sRes.json();
            const courses = await cRes.json();
            SearchSelect.populate('e_student',
                students.map(s => ({ value: s.id, label: `${s.roll_number || s.username}`, sub: `${s.first_name} ${s.last_name}` }))
            );
            SearchSelect.populate('e_course',
                courses.map(c => ({ value: c.id, label: `${c.code} — ${c.name}`, sub: `${c.credits} credits` }))
            );
        }
    }
}

async function assignCourseForTeacher(teacherId, teacherName) {
    await openModal('assignModal', { preTeacherId: teacherId, teacherName });
}

function closeModal(id) { document.getElementById(id).classList.remove('active'); }

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}


// ── Searchable Select Component ──────────────────────
// Converts a <select> into a text input with a filterable dropdown.
// Usage: SearchSelect.populate('selectId', [{value, label, sub}])

const SearchSelect = {
    _cache: {},

    /** Initialize a <select> as a searchable dropdown (called automatically by populate). */
    init(selectId) {
        const sel = document.getElementById(selectId);
        if (!sel || this._cache[selectId]) return;

        sel.style.display = 'none';

        const wrapper = document.createElement('div');
        wrapper.className = 'ss-wrap';
        sel.parentNode.insertBefore(wrapper, sel);

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'ss-input';
        input.placeholder = 'Type to search...';
        input.autocomplete = 'off';
        wrapper.appendChild(input);

        const list = document.createElement('div');
        list.className = 'ss-list';
        wrapper.appendChild(list);

        this._cache[selectId] = { input, list, sel, items: [] };

        input.addEventListener('focus', () => {
            list.classList.add('open');
            this._render(selectId, '');
        });

        input.addEventListener('input', () => {
            list.classList.add('open');
            sel.value = '';  // Clear selection while typing
            this._render(selectId, input.value);
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) list.classList.remove('open');
        });
    },

    /** Set items and reset the search input. */
    populate(selectId, items) {
        this.init(selectId);
        const c = this._cache[selectId];
        if (!c) return;
        c.items = items;
        c.input.value = '';
        c.sel.innerHTML = '<option value=""></option>' +
            items.map(i => `<option value="${i.value}"></option>`).join('');
        c.sel.value = '';
        this._render(selectId, '');
    },

    /** Render filtered items into the dropdown list. */
    _render(selectId, query) {
        const c = this._cache[selectId];
        if (!c) return;
        const q = query.toLowerCase();

        const filtered = q
            ? c.items.filter(i => i.label.toLowerCase().includes(q) || i.sub.toLowerCase().includes(q) || String(i.value).includes(q))
            : c.items;

        if (filtered.length === 0) {
            c.list.innerHTML = '<div class="ss-empty">No results found</div>';
            return;
        }

        c.list.innerHTML = filtered.map(i => `
            <div class="ss-item" data-val="${esc(i.value)}">
                <span class="ss-item-id">${esc(i.value)}</span>
                <span class="ss-item-label">${esc(i.label)}</span>
                <span class="ss-item-sub">${esc(i.sub)}</span>
            </div>
        `).join('');

        c.list.querySelectorAll('.ss-item').forEach(el => {
            el.addEventListener('click', () => {
                const v = el.dataset.val;
                const item = c.items.find(i => String(i.value) === v);
                c.sel.value = v;
                c.input.value = `[${v}] ${item ? item.label : v}`;
                c.list.classList.remove('open');
            });
        });
    }
};
