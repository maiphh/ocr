(() => {
    // Ensure a stable session ID and expose globally for debugging
    const GEN_ID = () => (typeof crypto !== 'undefined' && crypto.randomUUID)
        ? crypto.randomUUID()
        : String(Date.now()) + Math.random().toString(16).slice(2);
    const SESSION_ID = (typeof window !== 'undefined' && window.__OCR_SESSION_ID)
        ? window.__OCR_SESSION_ID
        : GEN_ID();
    if (typeof window !== 'undefined') {
        window.__OCR_SESSION_ID = SESSION_ID; // for debugging/inspection
    }

    // Inform backend to cleanup cached files when this tab unloads (reload/close)
    if (typeof window !== 'undefined') {
        const sendCleanup = () => {
            const payload = { sessionId: SESSION_ID };
            try {
                if (navigator && typeof navigator.sendBeacon === 'function') {
                    const data = JSON.stringify(payload);
                    const blob = new Blob([data], { type: 'application/json' });
                    const ok = navigator.sendBeacon(`/api/session/end?sessionID=${encodeURIComponent(SESSION_ID)}` , blob);
                    if (ok) return; // delivered
                }
            } catch (_) { /* fall through to fetch */ }
            // Fallback using keepalive fetch
            try {
                fetch(`/api/session/end?sessionID=${encodeURIComponent(SESSION_ID)}` , {
                    method: 'POST',
                    keepalive: true,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });
            } catch (_) { /* swallow */ }
        };
        window.addEventListener('beforeunload', sendCleanup);
        window.addEventListener('pagehide', sendCleanup);
    }
    const state = {
        schema: {},
        schemaOrder: [],
        results: [],
        preview: { available: false, error: null },
        rowIndex: new Map(),
        hasEdits: false,
    };

    const DEFAULT_COLUMN_CONFIG = {
        baseColumns: {
            index: false,
            originalFile: false,
            page: false,
            fileName: false,
            confidence: false,
            warnings: false,
        },
        hiddenSchemaFields: [],
    };

    const RESIZE_GRAB_AREA = 14;

    const normalizeBoolean = (value, fallback = true) => {
        if (value === undefined) return fallback;
        if (typeof value === "boolean") return value;
        if (typeof value === "number") {
            if (Number.isNaN(value)) return fallback;
            return value !== 0;
        }
        if (typeof value === "string") {
            const normalized = value.trim().toLowerCase();
            if (!normalized) {
                return fallback;
            }
            if (["false", "0", "off", "no", "n"].includes(normalized)) {
                return false;
            }
            if (["true", "1", "on", "yes", "y"].includes(normalized)) {
                return true;
            }
        }
        return Boolean(value);
    };

    const mergeColumnConfig = (overrides = {}) => {
        const baseColumns = {
            ...DEFAULT_COLUMN_CONFIG.baseColumns,
            ...(overrides.baseColumns || {}),
        };

        const rawHiddenFields =
            overrides.hiddenSchemaFields ?? DEFAULT_COLUMN_CONFIG.hiddenSchemaFields;

        const hiddenSchemaFields = Array.isArray(rawHiddenFields)
            ? rawHiddenFields
            : typeof rawHiddenFields === "string"
            ? rawHiddenFields.split(",")
            : DEFAULT_COLUMN_CONFIG.hiddenSchemaFields;

        const normalizedHiddenFields = hiddenSchemaFields
            .map((field) => String(field).trim())
            .filter((field) => field.length > 0);

        return {
            baseColumns,
            hiddenSchemaFields: normalizedHiddenFields,
        };
    };

    const getWindowConfig = () =>
        typeof window !== "undefined" ? window.ocrTableConfig || {} : {};

    let tableColumnConfig = mergeColumnConfig(getWindowConfig());

    const updateTableColumnConfig = (overrides = {}) => {
        if (typeof window === "undefined") {
            tableColumnConfig = mergeColumnConfig(overrides);
            return;
        }

        const current = window.ocrTableConfig || {};
        const merged = {
            baseColumns: {
                ...current.baseColumns,
                ...(overrides.baseColumns || {}),
            },
            hiddenSchemaFields:
                overrides.hiddenSchemaFields ?? current.hiddenSchemaFields,
        };
        window.ocrTableConfig = merged;
        tableColumnConfig = mergeColumnConfig(window.ocrTableConfig);

        if (Array.isArray(state.results)) {
            columnWidths.clear();
            buildTable(state.results);
        }
    };

    if (typeof window !== "undefined") {
        window.setOcrTableConfig = updateTableColumnConfig;
        window.resetOcrTableConfig = () => {
            window.ocrTableConfig = {};
            tableColumnConfig = mergeColumnConfig();
            columnWidths.clear();
            if (Array.isArray(state.results)) {
                buildTable(state.results);
            }
        };
    }

    const BASE_COLUMNS = [
        {
            key: "index",
            label: "#",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 font-semibold text-slate-700",
            render: (_row, index) => String(index + 1),
        },
        {
            key: "originalFile",
            label: "Original File",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 text-slate-700 break-words",
            render: (row) => row.originalName || "—",
        },
        {
            key: "page",
            label: "Page",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 text-slate-700",
            render: (row) => row.pageLabel || `Page ${row.pageNumber ?? 1}`,
        },
        {
            key: "fileName",
            label: "File Name",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 text-slate-700 break-words",
            render: (row) => row.fileName || "—",
        },
        {
            key: "confidence",
            label: "Confidence",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 text-slate-700",
            render: (row) => row.confidenceDisplay ?? "—",
        },
        {
            key: "warnings",
            label: "Warnings",
            headerClassName: "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
            cellClassName: "px-4 py-3 text-slate-600",
            render: (row) => (row.warnings?.length ? row.warnings.join(", ") : "—"),
        },
    ];

    const columnWidths = new Map();
    const MIN_COLUMN_WIDTH = 80;
    let resizeState = null;

    let activePreviewKey = null;
    let activePreviewPage = 1;
    let previewAbortController = null;

    let selectedRowKey = null;
    let selectedPage = 1;
    let activePreviewUrl = null;
    const pendingEdits = new Map();
    const AUTO_SAVE_DELAY = 2000;
    let autoSaveTimer = null;
    let savePromise = null;

    const dom = {
        navButtons: document.querySelectorAll(".nav-btn"),
        panels: document.querySelectorAll(".panel"),
        processForm: document.getElementById("process-form"),
        processBtn: document.getElementById("process-btn"),
        clearFilesBtn: document.getElementById("clear-files-btn"),
        fileInput: document.getElementById("document-files"),
        fileList: document.getElementById("file-list"),
        processStatus: document.getElementById("process-status"),
        resultsRegion: document.getElementById("results-region"),
        summaryTotal: document.getElementById("summary-total"),
        summaryConfidence: document.getElementById("summary-confidence"),
        summaryWarnings: document.getElementById("summary-warnings"),
        summaryProfile: document.getElementById("summary-profile"),
        downloadActions: document.getElementById("download-actions"),
        downloadExcelBtn: document.getElementById("download-excel"),
        downloadCsvBtn: document.getElementById("download-csv"),
        downloadJsonBtn: document.getElementById("download-json"),
        saveEditsBtn: document.getElementById("save-edits"),
        resultsStatus: document.getElementById("results-status"),
        resultsHead: document.getElementById("results-head"),
        resultsBody: document.getElementById("results-body"),
        resultsTableWrapper: document.getElementById("results-table-wrapper"),
        tableZoom: document.getElementById("table-zoom"),
        previewContent: document.getElementById("preview-content"),
        previewFooter: document.getElementById("preview-footer"),
        previewControls: document.getElementById("preview-controls"),
        previewPrev: document.getElementById("preview-prev"),
        previewNext: document.getElementById("preview-next"),
        previewPageIndicator: document.getElementById("preview-page-indicator"),
        previewZoom: document.getElementById("preview-zoom"),
        schemaCount: document.getElementById("schema-count"),
        schemaStatus: document.getElementById("schema-status"),
        schemaTabs: document.querySelectorAll("[data-schema-tab]"),
        schemaPanels: {
            fields: document.getElementById("schema-field-editor"),
            json: document.getElementById("schema-json-editor"),
        },
        schemaJson: document.getElementById("schema-json"),
        toggleAddField: document.getElementById("toggle-add-field"),
        addFieldForm: document.getElementById("add-field-form"),
        cancelAddField: document.getElementById("cancel-add-field"),
        fieldList: document.getElementById("schema-field-list"),
        addFieldInputs: {
            name: document.getElementById("new-field-name"),
            type: document.getElementById("new-field-type"),
            format: document.getElementById("new-field-format"),
            required: document.getElementById("new-field-required"),
            nullable: document.getElementById("new-field-nullable"),
            description: document.getElementById("new-field-description"),
        },
        applySchemaJson: document.getElementById("apply-schema-json"),
        reloadSchemaJson: document.getElementById("reload-schema-json"),
        resetSchema: document.getElementById("reset-schema"),
        exportSchema: document.getElementById("export-schema"),
        importSchema: document.getElementById("schema-import"),
    };

    const formatBytes = (bytes) => {
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
    };

    const toMessage = (error, fallback) => {
        if (error instanceof Error) {
            return error.message;
        }
        if (error === undefined || error === null) {
            return fallback;
        }
        return String(error);
    };

    const applyWidthToColumn = (columnKey, width) => {
        if (!Number.isFinite(width) || !dom.resultsHead) return;
        const headerCell = dom.resultsHead.querySelector(
            `[data-column-key="${columnKey}"]`,
        );
        if (!headerCell || !headerCell.parentElement) return;

        const headerRow = headerCell.parentElement;
        const columnIndex = Array.prototype.indexOf.call(
            headerRow.children,
            headerCell,
        );
        if (columnIndex === -1) return;
        const px = `${width}px`;
        headerCell.style.width = px;
        headerCell.style.minWidth = px;

        dom.resultsBody.querySelectorAll("tr").forEach((row) => {
            const cell = row.children[columnIndex];
            if (cell) {
                cell.style.width = px;
                cell.style.minWidth = px;
            }
        });
    };

    const onColumnResize = (event) => {
        if (!resizeState) return;
        const delta = event.pageX - resizeState.startX;
        const width = Math.max(MIN_COLUMN_WIDTH, resizeState.startWidth + delta);
        resizeState.currentWidth = width;
        applyWidthToColumn(resizeState.columnKey, width);
        event.preventDefault();
    };

    const stopColumnResize = () => {
        if (!resizeState) return;
        if (resizeState.headerCell) {
            resizeState.headerCell.classList.remove("resizing");
            resizeState.headerCell.style.cursor = "";
        }
        if (resizeState.currentWidth) {
            columnWidths.set(resizeState.columnKey, resizeState.currentWidth);
        }
        document.removeEventListener("mousemove", onColumnResize);
        document.removeEventListener("mouseup", stopColumnResize);
        document.body.classList.remove("cursor-col-resize");
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        resizeState = null;
    };

    const startColumnResize = (event, columnIndex, columnKey) => {
        const headerRow = dom.resultsHead?.firstElementChild;
        if (!headerRow) return;
        const headerCell = headerRow.children[columnIndex];
        if (!headerCell) return;

        const measuredWidth =
            headerCell.getBoundingClientRect().width || MIN_COLUMN_WIDTH;
        const startWidth = columnWidths.get(columnKey) ?? measuredWidth;
        resizeState = {
            columnIndex,
            columnKey,
            startX: event.pageX,
            startWidth,
            currentWidth: startWidth,
            headerCell,
        };

        headerCell.classList.add("resizing");
        document.addEventListener("mousemove", onColumnResize);
        document.addEventListener("mouseup", stopColumnResize);
        document.body.classList.add("cursor-col-resize");
        document.body.style.cursor = "col-resize";
        document.body.style.userSelect = "none";
        event.preventDefault();
        event.stopPropagation();
    };

    const setupColumnResizing = () => {
        const headerRow = dom.resultsHead?.firstElementChild;
        if (!headerRow) return;

        const presentKeys = new Set();

        Array.from(headerRow.children).forEach((th, index) => {
            const columnKey = th.dataset.columnKey || `col-${index}`;
            presentKeys.add(columnKey);
            th.classList.add("resizable-column", "pr-6");
            if (!th.querySelector(".column-resize-handle")) {
                const handle = document.createElement("span");
                handle.className = "column-resize-handle";
                handle.addEventListener("mousedown", (event) =>
                    startColumnResize(event, index, columnKey),
                );
                handle.addEventListener("click", (event) => event.preventDefault());
                th.appendChild(handle);
            }

            th.addEventListener("mousedown", (event) => {
                if (event.button !== 0) return;
                const rect = th.getBoundingClientRect();
                const offsetX = event.clientX - rect.left;
                if (rect.width - offsetX <= RESIZE_GRAB_AREA) {
                    startColumnResize(event, index, columnKey);
                }
            });

            th.addEventListener("mousemove", (event) => {
                if (resizeState?.columnKey === columnKey) {
                    th.style.cursor = "col-resize";
                    return;
                }
                const rect = th.getBoundingClientRect();
                const offsetX = event.clientX - rect.left;
                if (rect.width - offsetX <= RESIZE_GRAB_AREA) {
                    th.style.cursor = "col-resize";
                } else if (!resizeState) {
                    th.style.cursor = "";
                }
            });

            th.addEventListener("mouseleave", () => {
                if (!resizeState) {
                    th.style.cursor = "";
                }
            });

            if (!columnWidths.has(columnKey)) {
                const measuredWidth =
                    th.getBoundingClientRect().width || MIN_COLUMN_WIDTH;
                columnWidths.set(columnKey, Math.max(MIN_COLUMN_WIDTH, measuredWidth));
            }
            applyWidthToColumn(columnKey, columnWidths.get(columnKey));
        });

        Array.from(columnWidths.keys()).forEach((key) => {
            if (!presentKeys.has(key)) {
                columnWidths.delete(key);
            }
        });
    };

    const refreshSaveButtonState = () => {
        if (!dom.saveEditsBtn) return;
        if (state.hasEdits || pendingEdits.size > 0) {
            dom.saveEditsBtn.classList.remove("hidden");
            dom.saveEditsBtn.disabled = false;
            dom.saveEditsBtn.textContent = "Save edits";
        } else {
            dom.saveEditsBtn.classList.add("hidden");
        }
    };

    const scheduleAutoSave = () => {
        if (autoSaveTimer) {
            clearTimeout(autoSaveTimer);
        }
        autoSaveTimer = setTimeout(async () => {
            autoSaveTimer = null;
            if (!state.hasEdits) return;
            try {
                await saveEdits({ silent: true });
            } catch (error) {
                console.error("autosave failed", error);
            }
        }, AUTO_SAVE_DELAY);
    };

    const markPendingEdits = () => {
        if (!dom.saveEditsBtn) return;
        state.hasEdits = true;
        refreshSaveButtonState();
        setBanner(dom.resultsStatus, "You have unsaved edits.", "warning");
        scheduleAutoSave();
    };

    const recordPendingEdit = (fileKey, fieldName, value) => {
        if (!fileKey || !fieldName) return;
        let entry = pendingEdits.get(fileKey);
        if (!entry) {
            entry = {};
            pendingEdits.set(fileKey, entry);
        }
        entry[fieldName] = value;
    };

    const handleCellEdit = (event) => {
        const td = event.currentTarget;
        const fileKey = td.dataset.fileKey;
        const fieldName = td.dataset.field;
        if (!fileKey || !fieldName) return;

        const row = state.rowIndex.get(fileKey);
        if (!row) return;

        const newValue = td.innerText.trim();
        const previousValue = row.fields[fieldName] ?? "";
        if (newValue === previousValue) return;

        row.fields[fieldName] = newValue;
        const resultRow = state.results.find((entry) => entry.fileKey === fileKey);
        if (resultRow) {
            resultRow.fields[fieldName] = newValue;
        }
        recordPendingEdit(fileKey, fieldName, newValue);
        markPendingEdits();
    };

    const handleCellKeyDown = (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.blur();
        }
    };

    const setBanner = (element, message, tone = "info") => {
        if (!element) return;

        const baseClasses = [
            "rounded-2xl",
            "px-4",
            "py-3",
            "text-sm",
            "font-semibold",
            "shadow-sm",
            "transition",
        ];
        const toneClasses = {
            success: ["border", "border-emerald-200", "bg-emerald-50", "text-emerald-700"],
            error: ["border", "border-rose-200", "bg-rose-50", "text-rose-700"],
            warning: ["border", "border-[#B94828]/30", "bg-[#B94828]/10", "text-[#B94828]"],
            info: ["border", "border-[#B94828]/30", "bg-[#B94828]/10", "text-[#B94828]"],
        };

        if (!message) {
            element.textContent = "";
            element.className = "";
            element.classList.add("hidden");
            return;
        }

        element.className = "";
        element.classList.add(...baseClasses, ...(toneClasses[tone] || toneClasses.info));
        element.textContent = message;
        element.classList.remove("hidden");
    };

    const updateFileList = (files) => {
        dom.fileList.innerHTML = "";
        if (!files || !files.length) return;
        Array.from(files).forEach((file) => {
            const item = document.createElement("div");
            item.className = "flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600";
            item.innerHTML = `
                <span>${file.name}</span>
                <span>${formatBytes(file.size)}</span>
            `;
            dom.fileList.appendChild(item);
        });
    };

    const scrollToPanelTop = () => {
        window.scrollTo({ top: dom.resultsRegion?.offsetTop ?? 0, behavior: "smooth" });
    };

    const clearPreview = () => {
        selectedRowKey = null;
        selectedPage = 1;
        activePreviewKey = null;
        activePreviewPage = 1;
        if (previewAbortController) {
            previewAbortController.abort();
            previewAbortController = null;
        }
        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = null;
        }
        dom.previewContent.innerHTML = "Select a row to preview the processed page.";
        dom.previewControls.classList.add("hidden");
        dom.previewFooter.textContent = "";
        dom.resultsBody.querySelectorAll("tr").forEach((row) => {
            row.classList.remove("bg-[#B94828]/10", "ring-1", "ring-[#B94828]/20");
            row.classList.add("bg-white");
        });
    };

    const updateSummary = (summary, meta) => {
        dom.summaryTotal.textContent = summary.totalFiles ?? 0;
        const confidencePercent = ((summary.averageConfidence ?? 0) * 100).toFixed(1);
        dom.summaryConfidence.textContent = `${confidencePercent}%`;
        dom.summaryWarnings.textContent = summary.warningsCount ?? 0;
        const profile = `${meta.ocr_engine ?? "–"} · ${(meta.ocr_languages || []).join(", ")}`;
        dom.summaryProfile.textContent = profile;
    };

    const buildTable = (rows) => {
        const normalizedRows = rows.map((row) => {
            const overrides = pendingEdits.get(row.fileKey);
            const mergedFields = { ...(row.fields || {}) };
            if (overrides) {
                Object.entries(overrides).forEach(([fieldName, value]) => {
                    mergedFields[fieldName] = value;
                });
            }
            return {
                ...row,
                fields: mergedFields,
            };
        });

        state.results = normalizedRows;
        dom.resultsHead.innerHTML = "";
        dom.resultsBody.innerHTML = "";
        state.rowIndex.clear();

        if (!state.schemaOrder.length && normalizedRows[0]?.fields) {
            state.schemaOrder = Object.keys(normalizedRows[0].fields);
        }

        if (dom.tableZoom) {
            const scale = Number(dom.tableZoom.value || 100) / 100;
            if (dom.resultsTableWrapper) {
                dom.resultsTableWrapper.style.setProperty("--table-scale", scale);
            }
        }

        const hiddenSchemaConfig = tableColumnConfig?.hiddenSchemaFields ?? [];
        const hiddenSchemaArray = Array.isArray(hiddenSchemaConfig)
            ? hiddenSchemaConfig
            : typeof hiddenSchemaConfig === "string"
            ? hiddenSchemaConfig.split(",")
            : [];

        const hiddenSchemaFields = new Set(
            hiddenSchemaArray
                .map((field) => String(field).trim())
                .filter((field) => field.length > 0),
        );
        const visibleSchemaFields = state.schemaOrder.filter(
            (field) => !hiddenSchemaFields.has(String(field).trim()),
        );

        const baseOverrides = tableColumnConfig?.baseColumns ?? {};
        let visibleBaseColumns = BASE_COLUMNS.filter((column) =>
            normalizeBoolean(baseOverrides[column.key], true),
        );

        if (!visibleBaseColumns.length && !visibleSchemaFields.length) {
            visibleBaseColumns = BASE_COLUMNS.filter((column) => column.key === "index");
        }

        const headerRow = document.createElement("tr");

        visibleBaseColumns.forEach((column) => {
            const th = document.createElement("th");
            th.textContent = column.label;
            th.className = column.headerClassName;
            th.dataset.columnKey = column.key;
            headerRow.appendChild(th);
        });

        visibleSchemaFields.forEach((fieldName) => {
            const th = document.createElement("th");
            th.textContent = fieldName;
            th.className = "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500";
            th.dataset.columnKey = `field:${fieldName}`;
            headerRow.appendChild(th);
        });

        dom.resultsHead.appendChild(headerRow);

        const totalVisibleColumns = headerRow.children.length || 1;

        if (!normalizedRows.length) {
            const emptyRow = document.createElement("tr");
            emptyRow.className = "bg-white";
            const cell = document.createElement("td");
            cell.colSpan = totalVisibleColumns;
            cell.textContent = "No results.";
            cell.className = "px-4 py-3 text-sm text-slate-500";
            emptyRow.appendChild(cell);
            dom.resultsBody.appendChild(emptyRow);
            setupColumnResizing();
            refreshSaveButtonState();
            return;
        }

        normalizedRows.forEach((row, index) => {
            const tr = document.createElement("tr");
            tr.dataset.fileKey = row.fileKey;
            tr.className = "bg-white transition hover:bg-[#B94828]/5 cursor-pointer";

            visibleBaseColumns.forEach((column) => {
                const td = document.createElement("td");
                td.className = column.cellClassName;
                const value = column.render(row, index);
                td.textContent = value !== undefined && value !== null ? String(value) : "";
                tr.appendChild(td);
            });

            visibleSchemaFields.forEach((fieldName) => {
                const td = document.createElement("td");
                const value = row.fields[fieldName];
                td.textContent = value !== undefined && value !== null ? String(value) : "";
                td.className = "px-4 py-3 text-slate-700 align-top";
                td.contentEditable = "true";
                td.dataset.fileKey = row.fileKey;
                td.dataset.field = fieldName;
                td.addEventListener("blur", handleCellEdit);
                td.addEventListener("keydown", handleCellKeyDown);
                tr.appendChild(td);
            });

            tr.addEventListener("click", () => selectRow(row.fileKey));
            dom.resultsBody.appendChild(tr);
            state.rowIndex.set(row.fileKey, row);
        });

        const currentSelection = selectedRowKey;
        if (currentSelection) {
            if (state.rowIndex.has(currentSelection)) {
                selectRow(currentSelection);
            } else {
                clearPreview();
            }
        }

        setupColumnResizing();
        refreshSaveButtonState();
    };

    const renderPreview = async (row, page = 1, force = false) => {
        if (!row) return;
        const sameContext =
            activePreviewKey === row.fileKey && activePreviewPage === page;
        if (sameContext && !force) {
            return;
        }

        activePreviewKey = row.fileKey;
        activePreviewPage = page;

        if (previewAbortController) {
            previewAbortController.abort();
            previewAbortController = null;
        }

        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = null;
        }

        const descriptor = row.pageLabel
            ? `${row.fileName} · ${row.pageLabel}`
            : row.fileName;
        const warnings = Array.isArray(row.warnings) ? row.warnings : [];
        dom.previewFooter.textContent = warnings.length
            ? `Warnings: ${warnings.join(", ")}`
            : `File: ${descriptor}`;

        if (state.preview.available) {
            const controller = new AbortController();
            previewAbortController = controller;
            try {
                const response = await fetch(
                    `/api/preview/${row.fileKey}?page=${page}`,
                    { signal: controller.signal },
                );
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                const blob = await response.blob();
                activePreviewUrl = URL.createObjectURL(blob);
                dom.previewContent.innerHTML = `<img src="${activePreviewUrl}" alt="PDF preview page ${page}" class="w-full rounded-xl object-contain border border-slate-200 shadow-sm transition-transform duration-200">`;
                if (dom.previewZoom) {
                    const scale = Number(dom.previewZoom.value || 100) / 100;
                    dom.previewContent.firstElementChild.style.transform = `scale(${scale})`;
                    dom.previewContent.firstElementChild.style.transformOrigin = "top center";
                }
            } catch (error) {
                if (error && typeof error === "object" && "name" in error && error.name === "AbortError") {
                    return;
                }
                const message = error instanceof Error ? error.message : String(error);
                dom.previewContent.innerHTML = `
                    <div class="text-center text-sm font-medium text-rose-600">Preview unavailable: ${message}</div>
                `;
            } finally {
                if (previewAbortController === controller) {
                    previewAbortController = null;
                }
            }
        } else {
            dom.previewContent.innerHTML = `
                <div class="flex w-full flex-col items-center gap-3">
                    <iframe src="/api/preview/${row.fileKey}/pdf" title="${row.fileName}" class="h-[520px] w-full rounded-xl border border-slate-200 bg-white transition-transform duration-200"></iframe>
                    <p class="text-xs text-slate-500">Image preview disabled. Showing embedded PDF instead.</p>
                </div>
            `;
            if (state.preview.error) {
                dom.previewFooter.textContent = state.preview.error;
            }
            if (dom.previewZoom) {
                const scale = Number(dom.previewZoom.value || 100) / 100;
                const frame = dom.previewContent.querySelector("iframe");
                if (frame) {
                    frame.style.transform = `scale(${scale})`;
                    frame.style.transformOrigin = "top left";
                    frame.style.height = `${520 * scale}px`;
                }
            }
        }

        const pageCount = row.pageCount ?? row.totalPages ?? row.pages ?? 1;
        const totalPages = pageCount || 1;
        const displayPage = totalPages > 1 ? page : row.pageNumber ?? page;
        if (totalPages > 1 && state.preview.available) {
            dom.previewControls.classList.remove("hidden");
            const clampedPage = Math.min(page, totalPages);
            dom.previewPageIndicator.textContent = `Page ${clampedPage} / ${totalPages}`;
        } else {
            dom.previewControls.classList.add("hidden");
            dom.previewPageIndicator.textContent = `Page ${displayPage} / ${totalPages}`;
        }
    };

    const selectRow = (fileKey, options = {}) => {
        const row = state.rowIndex.get(fileKey);
        if (!row) return;

        const wasSelected = selectedRowKey === fileKey;
        selectedRowKey = fileKey;
        const maxPages = row.pageCount || row.totalPages || row.pages || 1;
        const nextPage = wasSelected ? Math.min(selectedPage, maxPages) || 1 : 1;
        const pageChanged = nextPage !== selectedPage;
        selectedPage = nextPage;

        dom.resultsBody.querySelectorAll("tr").forEach((tr) => {
            const isActive = tr.dataset.fileKey === fileKey;
            if (isActive) {
                tr.classList.add("bg-[#B94828]/10", "ring-1", "ring-[#B94828]/20");
                tr.classList.remove("bg-white");
            } else {
                tr.classList.remove("bg-[#B94828]/10", "ring-1", "ring-[#B94828]/20");
                tr.classList.add("bg-white");
            }
        });

        if (options.force || !wasSelected || pageChanged) {
            renderPreview(row, selectedPage, options.force === true);
        }
    };

    const processDocuments = async (event) => {
        event.preventDefault();
        const files = Array.from(dom.fileInput.files || []);
        if (!files.length) {
            setBanner(dom.processStatus, "Upload at least one PDF document.", "warning");
            return;
        }

        const ocrEngineValue = document.getElementById("ocr-engine").value || "easyocr";
        const ocrLanguagesValue = document.getElementById("ocr-languages").value || "en,vi";

        setBanner(dom.processStatus, `Preparing to process ${files.length} file(s)…`, "info");
        setBanner(dom.resultsStatus, "", "info");
        dom.processBtn.disabled = true;
        dom.processBtn.textContent = "Processing…";
        state.hasEdits = false;
        pendingEdits.clear();
        refreshSaveButtonState();

        let appendExisting = Array.isArray(state.results) && state.results.length > 0;

        for (let fileIndex = 0; fileIndex < files.length; fileIndex += 1) {
            const file = files[fileIndex];

            const initForm = new FormData();
            initForm.append("file", file, file.name);
            initForm.append("ocr_engine", ocrEngineValue);
            initForm.append("ocr_languages", ocrLanguagesValue);
            initForm.append("sessionId", SESSION_ID);

            setBanner(
                dom.processStatus,
                `Splitting "${file.name}" (${fileIndex + 1}/${files.length})…`,
                "info",
            );

            let jobMeta;
            try {
                const initResponse = await fetch("/api/process/split-init", {
                    method: "POST",
                    body: initForm,
                });
                if (!initResponse.ok) {
                    const detail = await initResponse.json().catch(() => ({}));
                    throw new Error(detail.detail || "Failed to prepare file.");
                }
                jobMeta = await initResponse.json();
            } catch (error) {
                const message = toMessage(error, "Unexpected error occurred.");
                setBanner(
                    dom.processStatus,
                    `Error preparing "${file.name}": ${message}`,
                    "error",
                );
                dom.processBtn.disabled = false;
                dom.processBtn.textContent = "Run pipeline";
                return;
            }

            const totalPages = Number(jobMeta.totalPages || 1);
            const jobId = jobMeta.jobId;

            for (let pageIndex = 0; pageIndex < totalPages; pageIndex += 1) {
                setBanner(
                    dom.processStatus,
                    `Processing "${file.name}" · Page ${pageIndex + 1}/${totalPages}`,
                    "info",
                );

                const nextPayload = {
                    jobId,
                    append: appendExisting || pageIndex > 0,
                    sessionId: SESSION_ID,
                };

                try {
                    const nextResponse = await fetch("/api/process/split-next", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(nextPayload),
                    });
                    if (!nextResponse.ok) {
                        const detail = await nextResponse.json().catch(() => ({}));
                        throw new Error(detail.detail || "Failed to process page.");
                    }
                    const payload = await nextResponse.json();
                    if (payload.done && !payload.table) {
                        continue;
                    }

                    const latestRow = payload.latestRow || (payload.table?.length ? payload.table[payload.table.length - 1] : null);

                    if (payload.done && !latestRow) {
                        continue;
                    }

                    if (!payload.table || !payload.table.length) {
                        continue;
                    }

                    state.results = payload.table;
                    state.preview = payload.pdfPreview;

                    updateSummary(payload.summary, payload.meta);
                    buildTable(payload.table);
                    dom.resultsRegion.classList.remove("hidden");
                    dom.downloadActions.classList.toggle("hidden", !payload.summary.totalFiles);
                    setBanner(dom.resultsStatus, "", "info");

                    const hasExistingSelection =
                        selectedRowKey !== null && state.rowIndex.has(selectedRowKey);

                    if (latestRow && !hasExistingSelection) {
                        selectRow(latestRow.fileKey, { force: true });
                    }

                    if (fileIndex === 0 && pageIndex === 0) {
                        scrollToPanelTop();
                    }

                    setBanner(
                        dom.processStatus,
                        `Processed page ${pageIndex + 1}/${totalPages} of "${file.name}"`,
                        "success",
                    );
                } catch (error) {
                    const message = toMessage(error, "Unexpected error occurred.");
                    setBanner(
                        dom.processStatus,
                        `Error processing "${file.name}" (page ${pageIndex + 1}): ${message}`,
                        "error",
                    );
                    dom.processBtn.disabled = false;
                    dom.processBtn.textContent = "Run pipeline";
                    return;
                }

                appendExisting = true;
            }

        setBanner(
            dom.processStatus,
            `Completed "${file.name}" (${fileIndex + 1}/${files.length}).`,
            "success",
        );
    }

    setBanner(dom.processStatus, "All files processed successfully.", "success");
    dom.processBtn.disabled = false;
    dom.processBtn.textContent = "Run pipeline";
};

    const toggleAddFieldForm = (show) => {
        dom.addFieldForm.classList.toggle("hidden", !show);
        dom.toggleAddField.classList.toggle("hidden", show);
        if (!show) {
            dom.addFieldForm.reset();
            dom.addFieldInputs.nullable.checked = true;
            dom.addFieldInputs.type.value = "string";
            dom.addFieldInputs.format.value = "";
        }
    };

    const updateSchemaState = (schema) => {
        state.schema = schema;
        state.schemaOrder = Object.keys(schema);
        dom.schemaCount.textContent = state.schemaOrder.length;
        dom.schemaJson.value = JSON.stringify(schema, null, 2);
        renderFieldList();
    };

    const renderFieldList = () => {
        dom.fieldList.innerHTML = "";
        state.schemaOrder.forEach((fieldName) => {
            const config = state.schema[fieldName];
            const card = document.createElement("div");
            card.className = "rounded-3xl border border-brand/10 bg-white p-5 shadow-sm space-y-3";

            const header = document.createElement("div");
            header.className = "flex items-start justify-between gap-4";

            const info = document.createElement("div");
            info.innerHTML = `
                <h4 class="text-lg font-semibold text-brand-dark">${fieldName}</h4>
                <p class="text-sm text-slate-500">${config.description || "No description provided."}</p>
                <span class="inline-flex rounded-full bg-brand/10 px-3 py-1 text-xs font-semibold text-brand-dark">${config.type || "string"}</span>
            `;

            const actions = document.createElement("div");
            actions.className = "flex gap-2";
            actions.innerHTML = `
                <button type="button" data-action="edit" class="inline-flex items-center rounded-full bg-brand text-white px-3 py-1.5 text-xs font-semibold shadow-[0_10px_25px_-12px_rgba(185,72,40,0.65)] hover:bg-brand-dark focus:outline-none focus-visible:ring">Edit</button>
                <button type="button" data-action="delete" class="inline-flex items-center rounded-full border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-600 hover:border-rose-300 hover:text-rose-700">Delete</button>
            `;

            header.appendChild(info);
            header.appendChild(actions);
            card.appendChild(header);

            const editContainer = document.createElement("div");
            editContainer.className = "hidden flex-col gap-3 border-t border-slate-200 pt-4";
            editContainer.innerHTML = `
                <div class="grid gap-4 sm:grid-cols-3">
                    <div>
                        <label class="text-xs font-semibold text-slate-600">Type</label>
                        <select data-role="type" class="mt-2 w-full rounded-2xl border-slate-200 bg-white text-sm shadow-sm focus:border-brand focus:ring-brand">
                            ${["string", "date", "number", "boolean"].map((opt) => `<option value="${opt}" ${config.type === opt ? "selected" : ""}>${opt}</option>`).join("")}
                        </select>
                    </div>
                    <div data-role="format-group" class="flex flex-col ${config.type === "date" ? "" : "hidden"}">
                        <label class="text-xs font-semibold text-slate-600">Format</label>
                        <input type="text" data-role="format" value="${config.format || ""}" placeholder="iso-date" class="mt-2 w-full rounded-2xl border-slate-200 bg-white text-sm shadow-sm focus:border-brand focus:ring-brand">
                    </div>
                    <div class="flex items-center gap-4 text-sm text-slate-600">
                        <label class="inline-flex items-center gap-2">
                            <input type="checkbox" data-role="required" ${config.required ? "checked" : ""} class="rounded border-slate-300 text-brand focus:ring-brand">
                            Required
                        </label>
                        <label class="inline-flex items-center gap-2">
                            <input type="checkbox" data-role="nullable" ${config.nullable ? "checked" : ""} class="rounded border-slate-300 text-brand focus:ring-brand">
                            Nullable
                        </label>
                    </div>
                </div>
                <div>
                    <label class="text-xs font-semibold text-slate-600">Description</label>
                    <textarea rows="3" data-role="description" class="mt-2 w-full rounded-2xl border-slate-200 bg-white text-sm shadow-sm focus:border-brand focus:ring-brand">${config.description || ""}</textarea>
                </div>
                <div class="flex justify-end gap-2">
                    <button type="button" data-action="cancel" class="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-[#B94828] hover:text-[#B94828]">Cancel</button>
                    <button type="button" data-action="save" class="inline-flex items-center rounded-full bg-brand text-white px-3 py-1.5 text-xs font-semibold shadow-[0_10px_25px_-12px_rgba(185,72,40,0.65)] hover:bg-brand-dark">Save</button>
                </div>
            `;

            card.appendChild(editContainer);

            const editButton = actions.querySelector('[data-action="edit"]');
            const deleteButton = actions.querySelector('[data-action="delete"]');
            const saveButton = editContainer.querySelector('[data-action="save"]');
            const cancelButton = editContainer.querySelector('[data-action="cancel"]');
            const typeSelect = editContainer.querySelector('[data-role="type"]');
            const formatGroup = editContainer.querySelector('[data-role="format-group"]');
            const formatInput = editContainer.querySelector('[data-role="format"]');
            const requiredInput = editContainer.querySelector('[data-role="required"]');
            const nullableInput = editContainer.querySelector('[data-role="nullable"]');
            const descriptionInput = editContainer.querySelector('[data-role="description"]');

            deleteButton.addEventListener("click", () => deleteField(fieldName));

            editButton.addEventListener("click", () => {
                editContainer.classList.remove("hidden");
                editButton.classList.add("hidden");
            });

            cancelButton.addEventListener("click", () => {
                editContainer.classList.add("hidden");
                editButton.classList.remove("hidden");
                typeSelect.value = config.type || "string";
                if (formatInput) {
                    formatInput.value = config.format || "";
                }
                requiredInput.checked = Boolean(config.required);
                nullableInput.checked = Boolean(config.nullable);
                descriptionInput.value = config.description || "";
                if (config.type === "date") {
                    formatGroup.classList.remove("hidden");
                } else {
                    formatGroup.classList.add("hidden");
                }
            });

            typeSelect.addEventListener("change", () => {
                if (typeSelect.value === "date") {
                    formatGroup.classList.remove("hidden");
                } else {
                    formatGroup.classList.add("hidden");
                }
            });

            saveButton.addEventListener("click", () => {
                const description = descriptionInput.value.trim();
                const required = requiredInput.checked;
                const nullable = nullableInput.checked;
                const type = typeSelect.value;
                const format = formatInput ? formatInput.value.trim() : "";

                const originalConfig = state.schema[fieldName] || {};
                const updatedConfig = { ...originalConfig };
                updatedConfig.type = type;
                updatedConfig.required = required;

                if (description) {
                    updatedConfig.description = description;
                } else {
                    delete updatedConfig.description;
                }

                if (nullable) {
                    updatedConfig.nullable = true;
                } else {
                    delete updatedConfig.nullable;
                }

                if (type === "date") {
                    if (format) {
                        updatedConfig.format = format;
                    } else {
                        delete updatedConfig.format;
                    }
                } else {
                    delete updatedConfig.format;
                }

                updateField(fieldName, updatedConfig);
            });

            dom.fieldList.appendChild(card);
        });
    };

    const fetchSchema = async () => {
        try {
            const response = await fetch("/api/schema");
            if (!response.ok) {
                throw new Error("Unable to load schema.");
            }
            const data = await response.json();
            updateSchemaState(data.schema);
        } catch (error) {
            console.error(error);
            const message = toMessage(error, "Failed to load schema.");
            setBanner(dom.schemaStatus, message, "error");
        }
    };

const addField = async (event) => {
        event.preventDefault();
        const payload = {
            name: dom.addFieldInputs.name.value.trim(),
            type: dom.addFieldInputs.type.value,
            description: dom.addFieldInputs.description.value.trim() || null,
            required: dom.addFieldInputs.required.checked,
            nullable: dom.addFieldInputs.nullable.checked,
            format: dom.addFieldInputs.format.value.trim() || null,
        };

        if (!payload.name) {
            setBanner(dom.schemaStatus, "Field name cannot be empty.", "warning");
            return;
        }

        try {
            const response = await fetch("/api/schema/fields", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                throw new Error(detail.detail || "Failed to add field.");
            }
            const data = await response.json();
            updateSchemaState(data.schema);
            setBanner(dom.schemaStatus, `Field "${payload.name}" added.`, "success");
            toggleAddFieldForm(false);
        } catch (error) {
            const message = toMessage(error, "Unable to add field.");
            setBanner(dom.schemaStatus, message, "error");
        }
};

const deleteField = async (fieldName) => {
    if (!confirm(`Remove field "${fieldName}" from schema?`)) return;
    try {
        const response = await fetch(`/api/schema/fields/${encodeURIComponent(fieldName)}`, {
            method: "DELETE",
        });
        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(detail.detail || "Failed to delete field.");
        }
        const data = await response.json();
        updateSchemaState(data.schema);
        setBanner(dom.schemaStatus, `Field "${fieldName}" removed.`, "success");
    } catch (error) {
        const message = toMessage(error, "Unable to delete field.");
        setBanner(dom.schemaStatus, message, "error");
    }
};

const updateField = async (fieldName, updatedConfig) => {
    const schemaSnapshot = { ...state.schema };
    schemaSnapshot[fieldName] = updatedConfig;

    try {
        const response = await fetch("/api/schema/set", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ schema: schemaSnapshot }),
        });
        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(detail.detail || "Failed to update field.");
        }
        const data = await response.json();
        updateSchemaState(data.schema);
        setBanner(dom.schemaStatus, `Field "${fieldName}" updated.`, "success");
    } catch (error) {
        const message = toMessage(error, "Unable to update field.");
        setBanner(dom.schemaStatus, message, "error");
    }
};

    const applySchemaJson = async () => {
        let parsed;
        try {
            parsed = JSON.parse(dom.schemaJson.value);
        } catch (error) {
            setBanner(dom.schemaStatus, "Invalid JSON syntax.", "error");
            return;
        }

        try {
            const response = await fetch("/api/schema/set", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ schema: parsed }),
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                throw new Error(detail.detail || "Failed to apply schema.");
            }
            const data = await response.json();
            updateSchemaState(data.schema);
            setBanner(dom.schemaStatus, "Schema updated successfully.", "success");
        } catch (error) {
            const message = toMessage(error, "Unable to apply schema JSON.");
            setBanner(dom.schemaStatus, message, "error");
        }
    };

    const resetSchema = async () => {
        if (!confirm("Reset schema to default configuration?")) return;
        try {
            const response = await fetch("/api/schema/reset", { method: "POST" });
            if (!response.ok) {
                throw new Error("Failed to reset schema.");
            }
            const data = await response.json();
            updateSchemaState(data.schema);
            setBanner(dom.schemaStatus, "Schema reset to default.", "success");
        } catch (error) {
            const message = toMessage(error, "Unable to reset schema.");
            setBanner(dom.schemaStatus, message, "error");
        }
    };

    const exportSchema = () => {
        const blob = new Blob([JSON.stringify(state.schema, null, 2)], {
            type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "schema.json";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const importSchema = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            const response = await fetch("/api/schema/set", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ schema: parsed }),
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                throw new Error(detail.detail || "Failed to import schema.");
            }
            const data = await response.json();
            updateSchemaState(data.schema);
            setBanner(dom.schemaStatus, "Schema imported.", "success");
        } catch (error) {
            const message = toMessage(error, "Unable to import schema.");
            setBanner(dom.schemaStatus, message, "error");
        } finally {
            event.target.value = "";
        }
    };

    const saveEdits = async (options = {}) => {
        const { silent = false } = options;
        const hasPending = state.hasEdits || pendingEdits.size > 0;
        if (!hasPending) {
            if (!silent) {
                setBanner(dom.resultsStatus, "No edits to save.", "info");
            }
            return state.results;
        }
        if (savePromise) {
            return savePromise;
        }

        if (autoSaveTimer) {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = null;
        }

        const button = dom.saveEditsBtn;
        if (!silent && button) {
            button.disabled = true;
            button.textContent = "Saving…";
            setBanner(dom.resultsStatus, "Saving your edits…", "info");
        }

        const payload = {
            table: state.results,
        };

        const pendingSnapshot = new Map();
        pendingEdits.forEach((fields, fileKey) => {
            pendingSnapshot.set(fileKey, { ...fields });
        });

        const previousSelection = selectedRowKey;

        const executeSave = async () => {
            try {
                const response = await fetch("/api/results/update", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    const detail = await response.json().catch(() => ({}));
                    throw new Error(detail.detail || "Failed to save edits.");
                }
                const data = await response.json();
                const updatedTable = data.table || [];
                pendingSnapshot.forEach((fields, fileKey) => {
                    const current = pendingEdits.get(fileKey);
                    if (!current) {
                        return;
                    }
                    Object.entries(fields).forEach(([fieldName, value]) => {
                        if (current[fieldName] === value) {
                            delete current[fieldName];
                        }
                    });
                    if (Object.keys(current).length === 0) {
                        pendingEdits.delete(fileKey);
                    }
                });
                const hasRemaining = pendingEdits.size > 0;
                state.hasEdits = hasRemaining;
                buildTable(updatedTable);
                if (button) {
                    button.disabled = false;
                    button.textContent = "Save edits";
                }
                if (!silent) {
                    if (hasRemaining) {
                        setBanner(dom.resultsStatus, "Some edits are still pending…", "warning");
                    } else {
                        setBanner(dom.resultsStatus, "Edits saved successfully.", "success");
                    }
                } else if (!hasRemaining) {
                    setBanner(dom.resultsStatus, "", "info");
                }
                if (previousSelection && state.rowIndex.has(previousSelection)) {
                    selectRow(previousSelection, { force: true });
                } else {
                    clearPreview();
                }
                if (hasRemaining) {
                    scheduleAutoSave();
                }
                return updatedTable;
            } catch (error) {
                const message = toMessage(error, "Unable to save edits.");
                setBanner(dom.resultsStatus, message, "error");
                if (button) {
                    button.disabled = false;
                    button.textContent = "Save edits";
                }
                throw error;
            } finally {
                savePromise = null;
            }
        };

        savePromise = executeSave();
        return savePromise;
    };

    const ensureEditsSaved = async () => {
        if (!(state.hasEdits || pendingEdits.size > 0)) {
            return state.results;
        }
        try {
            return await saveEdits({ silent: true });
        } catch (error) {
            console.error("autosave failed", error);
            throw error;
        }
    };

    const switchSchemaTab = (tabId) => {
        const activeTabClasses = ["bg-white", "text-brand-dark", "shadow-md"];
        const inactiveTabClasses = ["bg-transparent", "text-brand-dark/70", "shadow-none"];

        dom.schemaTabs.forEach((btn) => {
            const isActive = btn.dataset.schemaTab === tabId;
            btn.classList.remove(...activeTabClasses, ...inactiveTabClasses);
            btn.classList.add(...(isActive ? activeTabClasses : inactiveTabClasses));
        });

        Object.entries(dom.schemaPanels).forEach(([id, panel]) => {
            if (id === tabId) {
                panel.classList.remove("hidden");
            } else {
                panel.classList.add("hidden");
            }
        });
    };

    const initNavigation = () => {
        const activeClasses = [
            "bg-white/90",
            "text-[#B94828]",
            "shadow-xl",
            "border-white/70",
        ];
        const inactiveClasses = ["bg-transparent", "text-white/90", "border-white/40"];

        const setActiveButton = (button) => {
            dom.navButtons.forEach((btn) => {
                const isActive = btn === button;
                btn.classList.remove(...activeClasses, ...inactiveClasses);
                btn.classList.add(...(isActive ? activeClasses : inactiveClasses));
            });
        };

        const showPanel = (targetId) => {
            dom.panels.forEach((panel) => {
                if (panel.id === targetId) {
                    panel.classList.remove("hidden");
                } else {
                    panel.classList.add("hidden");
                }
            });
        };

        dom.navButtons.forEach((btn) => {
            btn.addEventListener("click", () => {
                setActiveButton(btn);
                showPanel(btn.dataset.target);
                window.scrollTo({ top: 0, behavior: "smooth" });
            });
        });

        const initialButton = dom.navButtons[0];
        if (initialButton) {
            setActiveButton(initialButton);
            showPanel(initialButton.dataset.target);
        }
    };

    const initPreviewControls = () => {
        dom.previewPrev.addEventListener("click", () => {
            const row = state.rowIndex.get(selectedRowKey);
            if (!row) return;
            selectedPage = Math.max(1, selectedPage - 1);
            renderPreview(row, selectedPage);
        });
        dom.previewNext.addEventListener("click", () => {
            const row = state.rowIndex.get(selectedRowKey);
            if (!row) return;
            selectedPage = Math.min(row.pageCount, selectedPage + 1);
            renderPreview(row, selectedPage);
        });
    };

    const initEvents = () => {
        initNavigation();
        initPreviewControls();

        dom.tableZoom?.addEventListener("input", () => {
            const scale = Number(dom.tableZoom.value || 100) / 100;
            if (dom.resultsTableWrapper) {
                dom.resultsTableWrapper.style.setProperty("--table-scale", scale);
            }
        });

        dom.previewZoom?.addEventListener("input", () => {
            const scale = Number(dom.previewZoom.value || 100) / 100;
            if (!dom.previewContent) return;
            if (dom.previewContent.firstElementChild instanceof HTMLImageElement) {
                dom.previewContent.firstElementChild.style.transform = `scale(${scale})`;
                dom.previewContent.firstElementChild.style.transformOrigin = "top left";
            } else if (dom.previewContent.firstElementChild instanceof HTMLDivElement) {
                const frame = dom.previewContent.querySelector("iframe");
                if (frame) {
                    frame.style.transform = `scale(${scale})`;
                    frame.style.transformOrigin = "top left";
                    frame.style.height = `${600 * scale}px`;
                }
            }
        });

        dom.fileInput.addEventListener("change", () => updateFileList(dom.fileInput.files));
        dom.clearFilesBtn.addEventListener("click", () => {
            dom.fileInput.value = "";
            updateFileList([]);
        });
        dom.processForm.addEventListener("submit", processDocuments);

        dom.toggleAddField.addEventListener("click", () => toggleAddFieldForm(true));
        dom.cancelAddField.addEventListener("click", () => toggleAddFieldForm(false));
        dom.addFieldForm.addEventListener("submit", addField);

        dom.schemaTabs.forEach((btn) => {
            btn.addEventListener("click", () => switchSchemaTab(btn.dataset.schemaTab));
        });

        dom.applySchemaJson.addEventListener("click", applySchemaJson);
        dom.reloadSchemaJson.addEventListener("click", () => {
            dom.schemaJson.value = JSON.stringify(state.schema, null, 2);
            setBanner(dom.schemaStatus, "Schema JSON reloaded.", "info");
        });
        dom.resetSchema.addEventListener("click", resetSchema);
        dom.exportSchema.addEventListener("click", exportSchema);
        dom.importSchema.addEventListener("change", importSchema);
        dom.saveEditsBtn?.addEventListener("click", () => saveEdits());

        const triggerDownload = (href) => {
            const link = document.createElement("a");
            link.href = href;
            link.style.display = "none";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        };

        const bindDownload = (element) => {
            if (!element) return;
            element.addEventListener("click", async (event) => {
                const href = element.getAttribute("href");
                if (!href) {
                    return;
                }
                if (!state.results || !state.results.length) {
                    return;
                }
                event.preventDefault();
                try {
                    await ensureEditsSaved();
                    triggerDownload(href);
                } catch (error) {
                    // Error already surfaced via banner; do not trigger download.
                }
            });
        };

        bindDownload(dom.downloadExcelBtn);
        bindDownload(dom.downloadCsvBtn);
        bindDownload(dom.downloadJsonBtn);
    };

    const bootstrap = () => {
        initEvents();
        switchSchemaTab("fields");
        fetchSchema();
    };

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
