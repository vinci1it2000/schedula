import ajvRuntimeEqual from "ajv/dist/runtime/equal"
import {
    parseJson as ajvRuntimeparseJson,
    parseJsonNumber as ajvRuntimeparseJsonNumber,
    parseJsonString as ajvRuntimeparseJsonString
} from "ajv/dist/runtime/parseJson"
import ajvRuntimeQuote from "ajv/dist/runtime/quote"
// import ajvRuntimeRe2 from 'ajv/dist/runtime/re2';
import ajvRuntimeTimestamp from "ajv/dist/runtime/timestamp"
import ajvRuntimeUcs2length from "ajv/dist/runtime/ucs2length"
import ajvRuntimeUri from "ajv/dist/runtime/uri"
import * as ajvFormats from "ajv-formats/dist/formats"

// dependencies to replace in generated code, to be provided by at runtime
const validatorsBundleReplacements = {
    // '<code to be replaced>': ['<variable name to use as replacement>', <runtime dependency>],
    'require("ajv/dist/runtime/equal").default': [
        "ajvRuntimeEqual",
        ajvRuntimeEqual
    ],
    'require("ajv/dist/runtime/parseJson").parseJson': [
        "ajvRuntimeparseJson",
        ajvRuntimeparseJson
    ],
    'require("ajv/dist/runtime/parseJson").parseJsonNumber': [
        "ajvRuntimeparseJsonNumber",
        ajvRuntimeparseJsonNumber
    ],
    'require("ajv/dist/runtime/parseJson").parseJsonString': [
        "ajvRuntimeparseJsonString",
        ajvRuntimeparseJsonString
    ],
    'require("ajv/dist/runtime/quote").default': [
        "ajvRuntimeQuote",
        ajvRuntimeQuote
    ],
    // re2 by default is not in dependencies for ajv and so is likely not normally used
    // 'require("ajv/dist/runtime/re2").default': ['ajvRuntimeRe2', ajvRuntimeRe2],
    'require("ajv/dist/runtime/timestamp").default': [
        "ajvRuntimeTimestamp",
        ajvRuntimeTimestamp
    ],
    'require("ajv/dist/runtime/ucs2length").default': [
        "ajvRuntimeUcs2length",
        ajvRuntimeUcs2length
    ],
    'require("ajv/dist/runtime/uri").default': ["ajvRuntimeUri", ajvRuntimeUri],
    // formats
    'require("ajv-formats/dist/formats")': ["ajvFormats", ajvFormats]
}

const regexp = new RegExp(
    Object.keys(validatorsBundleReplacements)
        .map(key => key.replace(/[-\/\\^$*+?.()|[\]{}]/g, "\\$&"))
        .join("|"),
    "g"
)

function wrapAjvBundle(code) {
    return `function(${Object.values(validatorsBundleReplacements)
        .map(([name]) => name)
        .join(", ")}){\nvar exports = {};\n${code.replace(
        regexp,
        req => validatorsBundleReplacements[req][0]
    )};\nreturn exports;\n}`
}

const windowValidatorOnLoad = "__rjsf_validatorOnLoad"
const schemas = new Map()
if (typeof window !== "undefined") {
    // @ts-ignore
    window[windowValidatorOnLoad] = (loadedId, fn) => {
        const validator = fn(
            ...Object.values(validatorsBundleReplacements).map(([, dep]) => dep)
        )
        let validatorLoader = schemas.get(loadedId)
        if (validatorLoader) {
            validatorLoader.resolve(validator)
        } else {
            throw new Error(`Unknown validator loaded id="${loadedId}"`)
        }
    }
}

/**
 * Evaluate precompiled validator in browser using script tag
 * @param id Identifier to avoid evaluating the same code multiple times
 * @param code Code generated server side using `compileSchemaValidatorsCode`
 * @param nonce nonce attribute to be added to script tag (https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/nonce#using_nonce_to_allowlist_a_script_element)
 */
export function evaluateValidator(id, code, nonce) {
    let maybeValidator = schemas.get(id)
    if (maybeValidator) return maybeValidator.promise
    let resolveValidator
    const validatorPromise = new Promise(resolve => {
        resolveValidator = resolve
    })
    schemas.set(id, {
        promise: validatorPromise,
        resolve: resolveValidator
    })

    const scriptElement = document.createElement("script")

    scriptElement.setAttribute("nonce", nonce)
    scriptElement.text = `window["${windowValidatorOnLoad}"]("${id}", ${wrapAjvBundle(
        code
    )})`

    document.body.appendChild(scriptElement)
    return validatorPromise
}
