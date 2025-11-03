import i18n from 'i18next';
import Backend from 'i18next-http-backend';
import po2i18next from 'gettext-converter/po2i18next'
import isString from "lodash/isString";
import {isObject} from "@rjsf/utils";

function joinPaths(path1, path2) {
    // If both paths have slashes at the join point, remove one
    if (path1.endsWith('/') && path2.startsWith('/')) {
        return path1 + path2.slice(1);
    }
    // If neither path has a slash at the join point, add one
    if (!path1.endsWith('/') && !path2.startsWith('/')) {
        return `${path1}/${path2}`;
    }
    // Otherwise, join as is
    return path1 + path2;
}

i18n.use(Backend).init({
    fallbackLng: 'en_US',
    lng: document.documentElement.lang,
    ns: 'messages',
    nsSeparator: ':::',
    defaultNS: 'messages',
    keySeparator: false,
    parseMissingKeyHandler: (key) => (
        key.startsWith(`messages:::`) ? key.slice(11) : key
    ),
    appendNamespaceToMissingKey: true,
    interpolation: {
        escapeValue: false, // not needed for react as it escapes by default
    },
    backend: {
        loadPath: (languages, namespaces) => {
            let url = '/locales/{{lng}}/{{ns}}'
            if (window.getPublicPath)
                url = joinPaths(window.getPublicPath(), url);
            return url
        },
        parse: function (data) {
            return po2i18next(data, {compatibilityJSON: 'v4'})
        }
    }
});

export function translateJSON(t, data, options) {
    if (isString(data)) {
        let newData = t(data, options)
        if (newData.startsWith('§')) {
            newData = eval(newData.slice(1))
        }
        return newData
    } else if (Array.isArray(data)) {
        return data.map(v => translateJSON(t, v, options))
    } else if (isObject(data)) {
        let newData = {}
        Object.entries(data).forEach(([k, v]) => {
            newData[k] = translateJSON(t, v, options)
        })
        return newData
    } else {
        return data
    }
}

export default i18n;
