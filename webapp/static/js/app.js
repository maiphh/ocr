(() => {
    const state = {
        schema: {},
        schemaOrder: [],
        results: [],
        preview: { available: false, error: null },
        rowIndex: new Map(),
    };

    let selectedRowKey = null;
    let selectedPage = 1;
    let activePreviewUrl = null;

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
        resultsHead: document.getElementById("results-head"),
        resultsBody: document.getElementById("results-body"),
        previewContent: document.getElementById("preview-content"),
        previewFooter: document.getElementById("preview-footer"),
        previewControls: document.getElementById("preview-controls"),
        previewPrev: document.getElementById("preview-prev"),
        previewNext: document.getElementById("preview-next"),
        previewPageIndicator: document.getElementById("preview-page-indicator"),
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
            warning: ["border", "border-amber-200", "bg-amber-50", "text-amber-700"],
            info: ["border", "border-brand/30", "bg-brand/10", "text-brand-dark"],
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
        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = null;
        }
        dom.previewContent.innerHTML = "Select a row to preview the processed page.";
        dom.previewControls.classList.add("hidden");
        dom.previewFooter.textContent = "";
        dom.resultsBody.querySelectorAll("tr").forEach((row) => {
            row.classList.remove("bg-brand/10", "ring-1", "ring-brand/20");
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
        dom.resultsHead.innerHTML = "";
        dom.resultsBody.innerHTML = "";
        state.rowIndex.clear();

        if (!rows.length) {
            const emptyRow = document.createElement("tr");
            emptyRow.className = "bg-white";
            const cell = document.createElement("td");
            cell.colSpan = 4;
            cell.textContent = "No results.";
            cell.className = "px-4 py-3 text-sm text-slate-500";
            emptyRow.appendChild(cell);
            dom.resultsBody.appendChild(emptyRow);
            return;
        }

        if (!state.schemaOrder.length && rows[0]?.fields) {
            state.schemaOrder = Object.keys(rows[0].fields);
        }

        const headerRow = document.createElement("tr");
        const headers = ["#", "File Name", "Confidence", "Warnings", ...state.schemaOrder];
        headers.forEach((label) => {
            const th = document.createElement("th");
            th.textContent = label;
            th.className = "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500";
            headerRow.appendChild(th);
        });
        dom.resultsHead.appendChild(headerRow);

        rows.forEach((row, index) => {
            const tr = document.createElement("tr");
            tr.dataset.fileKey = row.fileKey;
            tr.className = "bg-white transition hover:bg-brand/10 cursor-pointer";
            tr.innerHTML = `
                <td class="px-4 py-3 font-semibold text-slate-700">${index + 1}</td>
                <td class="px-4 py-3 text-slate-700">${row.fileName}</td>
                <td class="px-4 py-3 text-slate-700">${row.confidenceDisplay}</td>
                <td class="px-4 py-3 text-slate-600">${row.warnings.length ? row.warnings.join(", ") : "—"}</td>
            `;

            state.schemaOrder.forEach((fieldName) => {
                const td = document.createElement("td");
                const value = row.fields[fieldName];
                td.textContent = value !== undefined && value !== null ? String(value) : "";
                td.className = "px-4 py-3 text-slate-700 align-top";
                tr.appendChild(td);
            });

            tr.addEventListener("click", () => selectRow(row.fileKey));
            dom.resultsBody.appendChild(tr);
            state.rowIndex.set(row.fileKey, row);
        });
    };

    const renderPreview = async (row, page = 1) => {
        if (!row) return;
        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = null;
        }

        dom.previewFooter.textContent = row.warnings.length
            ? `Warnings: ${row.warnings.join(", ")}`
            : `File: ${row.fileName}`;

        if (state.preview.available) {
            try {
                const response = await fetch(`/api/preview/${row.fileKey}?page=${page}`);
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                const blob = await response.blob();
                activePreviewUrl = URL.createObjectURL(blob);
                dom.previewContent.innerHTML = `<img src="${activePreviewUrl}" alt="PDF preview page ${page}" class="h-full w-full rounded-xl object-contain">`;
            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                dom.previewContent.innerHTML = `
                    <div class="text-center text-sm font-medium text-rose-600">Preview unavailable: ${message}</div>
                `;
            }
        } else {
            dom.previewContent.innerHTML = `
                <div class="flex w-full flex-col items-center gap-3">
                    <iframe src="/api/preview/${row.fileKey}/pdf" title="${row.fileName}" class="h-80 w-full rounded-xl border border-slate-200 bg-white"></iframe>
                    <p class="text-xs text-slate-500">Image preview disabled. Showing embedded PDF instead.</p>
                </div>
            `;
            if (state.preview.error) {
                dom.previewFooter.textContent = state.preview.error;
            }
        }

        if (row.pageCount > 1 && state.preview.available) {
            dom.previewControls.classList.remove("hidden");
            dom.previewPageIndicator.textContent = `Page ${page} / ${row.pageCount}`;
        } else {
            dom.previewControls.classList.add("hidden");
            dom.previewPageIndicator.textContent = `Page ${page} / ${row.pageCount}`;
        }
    };

    const selectRow = (fileKey) => {
        const row = state.rowIndex.get(fileKey);
        if (!row) return;

        const isNewSelection = selectedRowKey !== fileKey;
        selectedRowKey = fileKey;
        selectedPage = isNewSelection ? 1 : Math.min(selectedPage, row.pageCount) || 1;

        dom.resultsBody.querySelectorAll("tr").forEach((tr) => {
            const isActive = tr.dataset.fileKey === fileKey;
            if (isActive) {
                tr.classList.add("bg-brand/10", "ring-1", "ring-brand/20");
                tr.classList.remove("bg-white");
            } else {
                tr.classList.remove("bg-brand/10", "ring-1", "ring-brand/20");
                tr.classList.add("bg-white");
            }
        });

        renderPreview(row, selectedPage);
    };

    const processDocuments = async (event) => {
        event.preventDefault();
        const files = dom.fileInput.files;
        if (!files.length) {
            setBanner(dom.processStatus, "Upload at least one PDF document.", "warning");
            return;
        }

        const formData = new FormData();
        Array.from(files).forEach((file) => formData.append("files", file));
        formData.append("ocr_engine", document.getElementById("ocr-engine").value);
        formData.append("ocr_languages", document.getElementById("ocr-languages").value || "en,vi");

        setBanner(dom.processStatus, "Processing documents… Sit tight.", "info");
        dom.processBtn.disabled = true;
        dom.processBtn.textContent = "Processing…";

        try {
            const response = await fetch("/api/process", {
                method: "POST",
                body: formData,
            });
            if (!response.ok) {
                const detail = await response.json().catch(() => ({}));
                throw new Error(detail.detail || "Failed to process documents.");
            }
            const payload = await response.json();
            state.results = payload.table;
            state.preview = payload.pdfPreview;

            updateSummary(payload.summary, payload.meta);
            buildTable(payload.table);
            setBanner(dom.processStatus, `Processed ${payload.summary.totalFiles} page(s) successfully.`, "success");
            dom.resultsRegion.classList.remove("hidden");
            dom.downloadActions.classList.toggle("hidden", !payload.summary.totalFiles);
            clearPreview();
            scrollToPanelTop();
        } catch (error) {
            console.error(error);
            const message = toMessage(error, "Unexpected error occurred.");
            setBanner(dom.processStatus, message, "error");
        } finally {
            dom.processBtn.disabled = false;
            dom.processBtn.textContent = "Run pipeline";
        }
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
            card.className = "rounded-3xl border border-slate-200 bg-slate-50 p-5 shadow-sm space-y-3";

            const required = config.required ? "Required" : "Optional";
            const nullable = config.nullable ? "Nullable" : "Non-nullable";
            const format = config.format ? ` · Format: ${config.format}` : "";
            const description = config.description || "—";

            card.innerHTML = `
                <div>
                    <h4 class="text-lg font-semibold text-slate-800">${fieldName}</h4>
                    <p class="mt-1 text-sm text-slate-500">${description}</p>
                </div>
                <div class="flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                    <span class="inline-flex rounded-full bg-white px-3 py-1">${config.type}</span>
                    <span class="inline-flex rounded-full bg-white px-3 py-1">${required}</span>
                    <span class="inline-flex rounded-full bg-white px-3 py-1">${nullable}</span>
                    ${format ? `<span class="inline-flex rounded-full bg-white px-3 py-1">${format}</span>` : ""}
                </div>
                <div class="flex justify-end">
                    <button type="button" data-field="${fieldName}" class="text-sm font-semibold text-rose-600 hover:text-rose-700">Remove</button>
                </div>
            `;

            card.querySelector("button").addEventListener("click", () => deleteField(fieldName));
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
        const activeClasses = ["bg-white/90", "text-brand-dark", "shadow-xl", "border-white/70"];
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
    };

    const bootstrap = () => {
        initEvents();
        switchSchemaTab("fields");
        fetchSchema();
    };

    document.addEventListener("DOMContentLoaded", bootstrap);
})();
