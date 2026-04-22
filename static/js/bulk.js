/* ── Bulk Editor — jspreadsheet CE v5 controller ── */

const BulkEditor = {
    _spreadsheet: null,   // the spreadsheet container instance
    _worksheet: null,     // the active worksheet (worksheets[0])
    _entity: null,
    _meta: {},    // dropdown source data cache

    /** Column configs for each entity */
    configs: {
        students: {
            endpoint: '/admin/bulk/students',
            fetchUrl: '/admin/students',
            idField: 'roll_number',
            columns: [
                { name: 'roll_number', title: 'Roll Number', width: 160,
                  readOnly: false  /* auto-generated for new rows; editable to allow lookup */
                },
                { name: 'first_name', title: 'First Name', width: 130 },
                { name: 'last_name', title: 'Last Name', width: 130 },
                { name: 'dob', title: 'DOB', width: 120, type: 'calendar', options: { format: 'YYYY-MM-DD' } },
                { name: 'branch_code', title: 'Branch', width: 90, type: 'dropdown', source: ['733','734','735','736','737','738'] },
                { name: 'email', title: 'Email', width: 180 },
                { name: 'phone', title: 'Phone', width: 130 },
                { name: 'gender', title: 'Gender', width: 90, type: 'dropdown', source: ['MALE','FEMALE','OTHER'] },
                { name: 'father_name', title: 'Father Name', width: 140 },
                { name: 'current_year', title: 'Year', width: 60 },
                { name: 'current_semester', title: 'Semester', width: 80 },
                { name: 'address', title: 'Address', width: 180 },
            ],
            mapRow(item) {
                return [
                    item.roll_number || '',
                    item.first_name || '',
                    item.last_name || '',
                    item.dob || '',
                    item.branch_code || '',
                    item.email || '',
                    item.phone || '',
                    item.gender || '',
                    item.father_name || '',
                    item.current_year || '',
                    item.current_semester || '',
                    item.address || '',
                ];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        },
        teachers: {
            endpoint: '/admin/bulk/teachers',
            fetchUrl: '/admin/teachers',
            idField: 'username',
            columns: [
                { name: 'username', title: 'Username', width: 150, readOnly: true },
                { name: 'first_name', title: 'First Name', width: 140 },
                { name: 'last_name', title: 'Last Name', width: 140 },
                { name: 'dob', title: 'DOB', width: 120, type: 'calendar', options: { format: 'YYYY-MM-DD' } },
                { name: 'email', title: 'Email', width: 200 },
                { name: 'phone', title: 'Phone', width: 140 },
                { name: 'department', title: 'Department', width: 180 },
            ],
            mapRow(item) {
                return [
                    item.username || '',
                    item.first_name || '',
                    item.last_name || '',
                    item.dob || '',
                    item.email || '',
                    item.phone || '',
                    item.department || '',
                ];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        },
        courses: {
            endpoint: '/admin/bulk/courses',
            fetchUrl: '/admin/courses',
            idField: 'code',
            columns: [
                { name: 'code', title: 'Code', width: 100 },
                { name: 'name', title: 'Name', width: 250 },
                { name: 'credits', title: 'Credits', width: 80 },
                { name: 'department', title: 'Department', width: 200 },
            ],
            mapRow(item) {
                return [item.code || '', item.name || '', item.credits || 3, item.department || ''];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        },
        offerings: {
            endpoint: '/admin/bulk/offerings',
            fetchUrl: '/admin/course-offerings',
            idField: 'id',
            columns: [
                { name: 'id', title: 'ID', width: 60, readOnly: true },
                { name: 'course_code', title: 'Course Code', width: 120, type: 'dropdown', source: [] },
                { name: 'academic_year', title: 'Acad. Year', width: 100 },
                { name: 'semester', title: 'Semester', width: 80 },
                { name: 'section', title: 'Section', width: 130, type: 'dropdown', source: [] },
                { name: 'capacity', title: 'Capacity', width: 80 },
                { name: 'start_date', title: 'Start Date', width: 120, type: 'calendar', options: { format: 'YYYY-MM-DD' } },
                { name: 'end_date', title: 'End Date', width: 120, type: 'calendar', options: { format: 'YYYY-MM-DD' } },
            ],
            mapRow(item) {
                const section = item.section_name && item.branch_code
                    ? `${item.branch_code}-${item.section_name}`
                    : '';
                return [
                    item.id || '',
                    item.course_code || '',
                    item.academic_year || '',
                    item.semester || '',
                    section,
                    item.capacity || 65,
                    item.start_date || '',
                    item.end_date || '',
                ];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        },
        enrollments: {
            endpoint: '/admin/bulk/enrollments',
            fetchUrl: '/admin/enrollments',
            idField: null,
            columns: [
                { name: 'student_roll', title: 'Student Roll', width: 170, type: 'dropdown', source: [] },
                { name: 'course_code', title: 'Course Code', width: 120, type: 'dropdown', source: [] },
                { name: 'academic_year', title: 'Acad. Year', width: 100 },
                { name: 'semester', title: 'Semester', width: 80 },
                { name: 'section', title: 'Section', width: 130, type: 'dropdown', source: [] },
            ],
            mapRow(item) {
                const section = item.section_name && item.branch_code
                    ? `${item.branch_code}-${item.section_name}`
                    : '';
                return [
                    item.roll_number || '',
                    item.course_code || '',
                    item.academic_year || '',
                    item.semester || '',
                    section,
                ];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        },
        assignments: {
            endpoint: '/admin/bulk/assignments',
            fetchUrl: '/admin/teacher-assignments',
            idField: null,
            columns: [
                { name: 'teacher_username', title: 'Teacher Username', width: 170, type: 'dropdown', source: [] },
                { name: 'course_code', title: 'Course Code', width: 120, type: 'dropdown', source: [] },
                { name: 'academic_year', title: 'Acad. Year', width: 100 },
                { name: 'semester', title: 'Semester', width: 80 },
                { name: 'section', title: 'Section', width: 130, type: 'dropdown', source: [] },
            ],
            mapRow(item) {
                const section = item.section_name && item.branch_code
                    ? `${item.branch_code}-${item.section_name}`
                    : '';
                return [
                    item.teacher_username || '',
                    item.course_code || '',
                    item.academic_year || '',
                    item.semester || '',
                    section,
                ];
            },
            mapPayload(rowData) {
                const cols = this.columns;
                const obj = {};
                cols.forEach((col, i) => { obj[col.name] = rowData[i] || ''; });
                return obj;
            }
        }
    },

    /** Populate dropdown sources from the API */
    async _loadMeta() {
        if (this._meta.loaded) return;
        const [cRes, sRes, stRes, tRes] = await Promise.all([
            api('/admin/courses'),
            api('/admin/sections'),
            api('/admin/students'),
            api('/admin/teachers'),
        ]);
        const courses = cRes ? await cRes.json() : [];
        const sections = sRes ? await sRes.json() : [];
        const students = stRes ? await stRes.json() : [];
        const teachers = tRes ? await tRes.json() : [];

        this._meta.courseCodes = courses.map(c => c.code);
        this._meta.sectionLabels = sections.map(s => `${s.branch_code}-${s.name}`);
        this._meta.studentRolls = students.map(s => s.roll_number || s.username);
        this._meta.teacherUsernames = teachers.map(t => t.username);
        this._meta.loaded = true;
    },

    /** Apply dynamic dropdown sources to column configs */
    _applyDropdowns(config) {
        const cols = JSON.parse(JSON.stringify(config.columns));
        cols.forEach(col => {
            if (col.name === 'course_code' && col.type === 'dropdown') {
                col.source = this._meta.courseCodes || [];
            }
            if ((col.name === 'section' ) && col.type === 'dropdown') {
                col.source = ['', ...this._meta.sectionLabels || []];
            }
            if (col.name === 'student_roll' && col.type === 'dropdown') {
                col.source = this._meta.studentRolls || [];
                col.autocomplete = true;
            }
            if (col.name === 'teacher_username' && col.type === 'dropdown') {
                col.source = this._meta.teacherUsernames || [];
                col.autocomplete = true;
            }
        });
        return cols;
    },

    /** Open the bulk editor for a given entity */
    async open(entity) {
        this._entity = entity;
        const config = this.configs[entity];
        if (!config) return;

        // Show modal
        document.getElementById('bulkEditModal').classList.add('active');
        document.getElementById('bulk-title').textContent = `Bulk Edit — ${entity.charAt(0).toUpperCase() + entity.slice(1)}`;
        document.getElementById('bulk-status').textContent = 'Loading...';
        document.getElementById('bulk-status').className = 'bulk-status';

        // Load metadata for dropdowns
        await this._loadMeta();

        // Fetch existing data
        const res = await api(config.fetchUrl);
        const existingData = res ? await res.json() : [];

        // Map to grid rows
        const dataRows = existingData.map(item => config.mapRow(item));

        // Add 10 empty rows for new entries
        const emptyCols = config.columns.length;
        for (let i = 0; i < 10; i++) {
            dataRows.push(new Array(emptyCols).fill(''));
        }

        // Build columns with dropdowns
        const columns = this._applyDropdowns(config);

        // Destroy previous instance
        const container = document.getElementById('spreadsheet');
        container.innerHTML = '';

        // v5 API: use worksheets array
        this._spreadsheet = jspreadsheet(container, {
            worksheets: [{
                data: dataRows,
                columns: columns,
                minDimensions: [columns.length, 5],
                tableOverflow: true,
                tableWidth: '100%',
                tableHeight: `${window.innerHeight - 200}px`,
                defaultColWidth: 120,
                allowInsertRow: true,
                allowDeleteRow: false,
                allowInsertColumn: false,
                allowDeleteColumn: false,
                columnSorting: false,
            }],
            contextMenu: function() { return false; },
        });

        // v5: worksheets is an array, get first worksheet
        this._worksheet = this._spreadsheet[0];

        // Track how many rows are existing (read-only IDs)
        this._existingCount = existingData.length;

        document.getElementById('bulk-status').textContent =
            `${existingData.length} existing rows loaded. Empty rows at bottom for new entries.`;
    },

    /** Close the bulk editor */
    close() {
        document.getElementById('bulkEditModal').classList.remove('active');
        const container = document.getElementById('spreadsheet');
        if (this._spreadsheet) {
            jspreadsheet.destroy(container);
            this._spreadsheet = null;
            this._worksheet = null;
        }
        container.innerHTML = '';
    },

    /** Save all rows */
    async save() {
        if (!this._worksheet || !this._entity) return;
        const config = this.configs[this._entity];
        const statusEl = document.getElementById('bulk-status');
        statusEl.textContent = 'Saving...';
        statusEl.className = 'bulk-status';

        // v5: getData() on the worksheet instance
        const allData = this._worksheet.getData();

        // Filter out completely empty rows
        const rows = [];
        const rowIndices = [];
        allData.forEach((rowData, idx) => {
            const hasContent = rowData.some(cell => cell !== null && cell !== undefined && String(cell).trim() !== '');
            if (hasContent) {
                rows.push(config.mapPayload(rowData));
                rowIndices.push(idx);
            }
        });

        if (rows.length === 0) {
            statusEl.textContent = 'No data to save.';
            statusEl.className = 'bulk-status bulk-status-warn';
            return;
        }

        // Call bulk endpoint
        const res = await api(config.endpoint, {
            method: 'POST',
            body: JSON.stringify(rows),
        });

        if (!res) {
            statusEl.textContent = 'Network error.';
            statusEl.className = 'bulk-status bulk-status-error';
            return;
        }

        const data = await res.json();

        // Apply row-level feedback
        if (data.results) {
            const totalCols = config.columns.length;

            data.results.forEach(result => {
                const gridRow = rowIndices[result.row];
                if (gridRow === undefined) return;

                let bgColor, textColor;
                if (result.status === 'error') {
                    bgColor = 'rgba(255,70,87,0.25)';
                    textColor = '#ffb6be';
                } else if (result.status === 'created') {
                    bgColor = 'rgba(34,199,122,0.2)';
                    textColor = '#80f0b4';
                } else if (result.status === 'updated') {
                    bgColor = 'rgba(100,149,237,0.2)';
                    textColor = '#a0c4ff';
                }

                if (bgColor) {
                    for (let c = 0; c < totalCols; c++) {
                        const cellId = BulkEditor._cellRef(c, gridRow);
                        try {
                            this._worksheet.setStyle(cellId, 'background-color', bgColor);
                            this._worksheet.setStyle(cellId, 'color', textColor);
                        } catch(e) { /* cell may not exist */ }
                    }
                }

                // Add error tooltip on first cell of errored row
                if (result.status === 'error' && result.message) {
                    try {
                        const cellId = BulkEditor._cellRef(0, gridRow);
                        this._worksheet.setComments(cellId, result.message);
                    } catch(e) { /* ignore */ }
                }
            });
        }

        const s = data.summary || {};
        const parts = [];
        if (s.created) parts.push(`${s.created} created`);
        if (s.updated) parts.push(`${s.updated} updated`);
        if (s.errors) parts.push(`${s.errors} errors`);

        statusEl.textContent = parts.join(', ') || 'Done';
        statusEl.className = s.errors
            ? 'bulk-status bulk-status-warn'
            : 'bulk-status bulk-status-success';

        if (s.errors) {
            statusEl.textContent += ' — hover over red cells to see error details';
        }
    },

    /** Convert col/row (0-indexed) to Excel-style cell ref like A1, B3, AA1 */
    _cellRef(col, row) {
        let letter = '';
        let c = col;
        while (c >= 0) {
            letter = String.fromCharCode(65 + (c % 26)) + letter;
            c = Math.floor(c / 26) - 1;
        }
        return letter + (row + 1);
    }
};
