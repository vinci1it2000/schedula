import {gzip, ungzip} from "pako";

/** -----------------------------
 *  Utilities
 *  ----------------------------- */
function isFileLike(v) {
    return (
        (typeof File !== "undefined" && v instanceof File) ||
        (typeof Blob !== "undefined" && v instanceof Blob)
    );
}

/**
 * Normalize `files` parameter into { [filename]: File|Blob }
 * Supported inputs:
 *  - { "a.pdf": File, "b.png": File }
 *  - [ File, File ]  (uses file.name)
 *  - [ { filename, file }, ... ]
 *  - [ { ref: "/files/a.pdf", file }, ... ]
 */
function normalizeFiles(files) {
    if (!files) return {};

    // Map already
    if (!Array.isArray(files) && typeof files === "object") {
        const out = {};
        for (const [k, v] of Object.entries(files)) {
            if (isFileLike(v)) out[k] = v;
        }
        return out;
    }

    // Array forms
    if (Array.isArray(files)) {
        const out = {};
        for (const entry of files) {
            if (isFileLike(entry)) {
                if (!entry.name) {
                    throw new Error("File in array must have a .name, or use {filename, file} form.");
                }
                out[entry.name] = entry;
            } else if (entry && typeof entry === "object" && isFileLike(entry.file)) {
                if (entry.filename) {
                    out[entry.filename] = entry.file;
                } else if (typeof entry.ref === "string") {
                    const m = entry.ref.match(/^\/files\/(.+)$/);
                    if (!m) throw new Error(`Invalid ref format: ${entry.ref}`);
                    out[m[1]] = entry.file;
                } else {
                    throw new Error("File entry must include {filename, file} or {ref, file}.");
                }
            }
        }
        return out;
    }

    return {};
}

/** -----------------------------
 *  Multipart builder:
 *   - payload: JSON (optionally gzipped) as Blob/Uint8Array
 *   - files: appended as "files[<filename>]"
 *  ----------------------------- */
function buildMultipartBody({data, filesByName, gzipPayload = true}) {
    const fd = new FormData();

    // payload
    if (gzipPayload) {
        const gz = gzip(JSON.stringify(data));
        fd.append(
            "payload",
            new Blob([gz], {type: "application/json"})
        );
        fd.append("payload_encoding", "gzip");
    } else {
        fd.append(
            "payload",
            new Blob([JSON.stringify(data)], {type: "application/json"})
        );
        fd.append("payload_encoding", "identity");
    }

    // files
    for (const [filename, file] of Object.entries(filesByName || {})) {
        // field name contains filename, so server can store by name easily
        // Example: files[invoice.pdf]
        fd.append(`files[${filename}]`, file, filename);
    }

    return fd;
}

/** -----------------------------
 *  Main request function
 *  ----------------------------- */
export default async function post(
    {
        url,
        data = {},           // JSON only; contains {$ref:"/files/<filename>"} but no actual File
        files = null,        // files separate
        form,
        headers,
        method = "POST",
        rawResponse = false,

        // NEW options
        gzipData = true,                 // for multipart, gzip only the payload part
        validateRefsHaveFiles = false,   // if true: every ref in data must exist in files map

        ...props
    }) {
    const filesByName = normalizeFiles(files);
    const hasFiles = method !== "GET" && Object.keys(filesByName).length > 0;

    const baseHeaders = {
        "X-CSRF-Token": form?.state?.csrf_token,
        "Accept-Encoding": "gzip",
        "Accept-Language": form?.state?.language,
        ...headers,
    };

    // Decide request mode:
    // - multipart when files exist
    // - gzip json otherwise (like before)
    const init = {
        method,
        crossDomain: true,
        cache: "no-cache",
        headers: {...baseHeaders},
        redirect: "follow",
        referrerPolicy: "unsafe-url",
    };

    if (method !== "GET") {
        if (hasFiles) {
            // multipart: DO NOT set content-type; browser sets boundary
            init.body = buildMultipartBody({
                data,
                filesByName,
                gzipPayload: gzipData,
            });

            // Ensure no wrong headers are forced
            delete init.headers["Content-Type"];
            delete init.headers["content-type"];
            delete init.headers["Content-Encoding"];
            delete init.headers["content-encoding"];
        } else {
            init.headers["Content-Type"] = "application/json";
            init.body = JSON.stringify(data);
            if (gzipData) {
                init.headers["Content-Encoding"] = "gzip";
                init.body = gzip(init.body);
            }
        }
    }

    // Keep your publicPath logic
    if (window.getPublicPath && url.startsWith("/")) {
        const publicPath = window.getPublicPath();
        if (publicPath.endsWith("/")) url = url.slice(1);
        url = `${publicPath}${url}`;
    }

    return fetch(url, {...init, ...props}).then(async (response) => {
        let debugUrl, messages;

        if (response.headers.has("Debug-Location")) {
            debugUrl = response.headers.get("Debug-Location");
        }

        if (response.headers.has("N-CSRF-Token")) {
            const csrf_token = response.headers.get("N-CSRF-Token");
            form?.setState?.((state) => ({...state, csrf_token}));
        }

        if (response.redirected) {
            window.location.href = response.url;
        }

        if (response.headers.has("X-Flash-Messages")) {
            messages = response.headers.get("X-Flash-Messages");
            if ((response.headers.get("X-Flash-Messages-Encoding") || "").includes("gzip")) {
                messages = ungzip(
                    Uint8Array.from(atob(messages), (c) => c.charCodeAt(0)),
                    {to: "string"}
                );
            }
            messages = JSON.parse(messages);
        }

        const contentType = response.headers.get("content-type") || "";
        const isJson = contentType.includes("application/json");

        if (response.status < 200 || response.status > 299) {
            let errors = {error: response.statusText};
            if (isJson) {
                errors = {...errors, ...(((await response.json()) || {}).response || {})};
            } else {
                try {
                    errors.detail = await response.text();
                } catch {
                }
            }
            return {data: errors, response, messages, debugUrl};
        }

        let parsed = rawResponse
            ? response
            : isJson
                ? await response.json()
                : await response.text();

        return {data: parsed, debugUrl, messages};
    });
}
