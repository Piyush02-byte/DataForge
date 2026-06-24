/**
 * DataForge — Frontend Application Logic
 * Vanilla JavaScript. No frameworks. No build tools.
 */

(function () {
    "use strict";

    // ─── DOM Elements ───────────────────────────────────────────────────
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const fileInfo = document.getElementById("file-info");
    const fileName = document.getElementById("file-name");
    const fileSize = document.getElementById("file-size");
    const removeFileBtn = document.getElementById("remove-file");
    const processBtn = document.getElementById("process-btn");

    const uploadSection = document.getElementById("upload-section");
    const processingSection = document.getElementById("processing-section");
    const resultsSection = document.getElementById("results-section");
    const errorSection = document.getElementById("error-section");

    const statInput = document.getElementById("stat-input");
    const statRejected = document.getElementById("stat-rejected");
    const statOutput = document.getElementById("stat-output");

    const downloadBtn = document.getElementById("download-btn");
    const resetBtn = document.getElementById("reset-btn");
    const errorMessage = document.getElementById("error-message");
    const errorRetryBtn = document.getElementById("error-retry-btn");

    // ─── State ──────────────────────────────────────────────────────────
    let selectedFile = null;
    let resultBlob = null;

    // ─── Drag & Drop ────────────────────────────────────────────────────
    dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove("drag-over");

        var files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files[0]);
        }
    });

    // Click to browse (delegate from drop zone, but not from the label/button)
    dropZone.addEventListener("click", function (e) {
        if (e.target === fileInput || e.target.classList.contains("browse-btn")) {
            return; // Let the label/input handle it
        }
        fileInput.click();
    });

    fileInput.addEventListener("change", function () {
        if (fileInput.files.length > 0) {
            handleFileSelection(fileInput.files[0]);
        }
    });

    // ─── File Selection ─────────────────────────────────────────────────
    function handleFileSelection(file) {
        // Validate extension
        if (!file.name.toLowerCase().endsWith(".csv")) {
            showError("Invalid file type. Please select a .csv file.");
            return;
        }

        // Validate size (25MB)
        if (file.size > 25 * 1024 * 1024) {
            showError("File is too large. Maximum size is 25MB.");
            return;
        }

        selectedFile = file;

        // Update UI
        fileName.textContent = file.name;
        fileSize.textContent = formatFileSize(file.size);
        dropZone.classList.add("hidden");
        fileInfo.classList.remove("hidden");
        processBtn.disabled = false;
    }

    function removeFile() {
        selectedFile = null;
        fileInput.value = "";
        dropZone.classList.remove("hidden");
        fileInfo.classList.add("hidden");
        processBtn.disabled = true;
    }

    removeFileBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        removeFile();
    });

    // ─── Process ────────────────────────────────────────────────────────
    processBtn.addEventListener("click", function () {
        if (!selectedFile) return;
        processFile(selectedFile);
    });

    async function processFile(file) {
        showProcessing();

        var formData = new FormData();
        formData.append("file", file);

        try {
            var response = await fetch("/process", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                var errorData;
                try {
                    errorData = await response.json();
                } catch (_) {
                    errorData = null;
                }
                var detail = errorData && errorData.detail
                    ? errorData.detail
                    : "Processing failed. Please check your file and try again.";
                showError(detail);
                return;
            }

            resultBlob = await response.blob();

            // Try to extract report from ZIP for stats display
            var report = await extractReportFromZip(resultBlob);
            showResults(report);
        } catch (err) {
            if (err.name === "TypeError" && err.message === "Failed to fetch") {
                showError("Cannot connect to server. Please make sure the server is running.");
            } else {
                showError("An unexpected error occurred. Please try again.");
            }
        }
    }

    // ─── ZIP Report Extraction ──────────────────────────────────────────
    async function extractReportFromZip(blob) {
        try {
            var arrayBuffer = await blob.arrayBuffer();
            var dataView = new DataView(arrayBuffer);

            // Find the End of Central Directory record
            var eocdOffset = findEOCD(dataView);
            if (eocdOffset === -1) return null;

            // Parse EOCD
            var centralDirOffset = dataView.getUint32(eocdOffset + 16, true);
            var numEntries = dataView.getUint16(eocdOffset + 10, true);

            // Parse central directory entries
            var offset = centralDirOffset;
            for (var i = 0; i < numEntries; i++) {
                var sig = dataView.getUint32(offset, true);
                if (sig !== 0x02014b50) break;

                var compMethod = dataView.getUint16(offset + 10, true);
                var compSize = dataView.getUint32(offset + 20, true);
                var uncompSize = dataView.getUint32(offset + 24, true);
                var nameLen = dataView.getUint16(offset + 28, true);
                var extraLen = dataView.getUint16(offset + 30, true);
                var commentLen = dataView.getUint16(offset + 32, true);
                var localHeaderOffset = dataView.getUint32(offset + 42, true);

                var nameBytes = new Uint8Array(arrayBuffer, offset + 46, nameLen);
                var entryName = new TextDecoder().decode(nameBytes);

                if (entryName === "report.json") {
                    // Parse local file header to find data start
                    var localNameLen = dataView.getUint16(localHeaderOffset + 26, true);
                    var localExtraLen = dataView.getUint16(localHeaderOffset + 28, true);
                    var dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;

                    var rawBytes = new Uint8Array(arrayBuffer, dataStart, compSize);

                    var jsonBytes;
                    if (compMethod === 8) {
                        // Deflate — use DecompressionStream
                        var ds = new DecompressionStream("deflate-raw");
                        var writer = ds.writable.getWriter();
                        writer.write(rawBytes);
                        writer.close();
                        var reader = ds.readable.getReader();
                        var chunks = [];
                        while (true) {
                            var result = await reader.read();
                            if (result.done) break;
                            chunks.push(result.value);
                        }
                        var totalLen = chunks.reduce(function (s, c) { return s + c.length; }, 0);
                        jsonBytes = new Uint8Array(totalLen);
                        var pos = 0;
                        for (var j = 0; j < chunks.length; j++) {
                            jsonBytes.set(chunks[j], pos);
                            pos += chunks[j].length;
                        }
                    } else {
                        // Stored (no compression)
                        jsonBytes = rawBytes;
                    }

                    var jsonStr = new TextDecoder().decode(jsonBytes);
                    return JSON.parse(jsonStr);
                }

                offset += 46 + nameLen + extraLen + commentLen;
            }

            return null;
        } catch (e) {
            // If ZIP parsing fails, just return null — download still works
            return null;
        }
    }

    function findEOCD(dataView) {
        // Search backwards for EOCD signature (0x06054b50)
        var len = dataView.byteLength;
        for (var i = len - 22; i >= Math.max(0, len - 65536); i--) {
            if (dataView.getUint32(i, true) === 0x06054b50) {
                return i;
            }
        }
        return -1;
    }

    // ─── Download ───────────────────────────────────────────────────────
    downloadBtn.addEventListener("click", function () {
        if (!resultBlob) return;

        var url = URL.createObjectURL(resultBlob);
        var a = document.createElement("a");
        a.href = url;
        a.download = "dataforge_results.zip";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // ─── Reset ──────────────────────────────────────────────────────────
    resetBtn.addEventListener("click", resetApp);
    errorRetryBtn.addEventListener("click", resetApp);

    function resetApp() {
        selectedFile = null;
        resultBlob = null;
        fileInput.value = "";

        uploadSection.classList.remove("hidden");
        processingSection.classList.add("hidden");
        resultsSection.classList.add("hidden");
        errorSection.classList.add("hidden");

        dropZone.classList.remove("hidden");
        fileInfo.classList.add("hidden");
        processBtn.disabled = true;
    }

    // ─── UI State Management ────────────────────────────────────────────
    function showProcessing() {
        uploadSection.classList.add("hidden");
        processingSection.classList.remove("hidden");
        resultsSection.classList.add("hidden");
        errorSection.classList.add("hidden");
    }

    function showResults(report) {
        processingSection.classList.add("hidden");
        resultsSection.classList.remove("hidden");

        if (report) {
            animateCounter(statInput, report.input_rows || 0);
            animateCounter(statRejected, report.rejected_rows || 0);
            animateCounter(statOutput, report.output_rows || 0);
        } else {
            statInput.textContent = "—";
            statRejected.textContent = "—";
            statOutput.textContent = "—";
        }
    }

    function showError(message) {
        uploadSection.classList.add("hidden");
        processingSection.classList.add("hidden");
        resultsSection.classList.add("hidden");
        errorSection.classList.remove("hidden");
        errorMessage.textContent = message;
    }

    // ─── Helpers ────────────────────────────────────────────────────────
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    function animateCounter(element, target) {
        var duration = 600;
        var start = 0;
        var startTime = null;

        function step(timestamp) {
            if (!startTime) startTime = timestamp;
            var progress = Math.min((timestamp - startTime) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
            var current = Math.round(eased * target);
            element.textContent = current.toLocaleString();
            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }

        requestAnimationFrame(step);
    }
})();
