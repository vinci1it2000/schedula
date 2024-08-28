import {createGlobalStore} from "hox";
import {useState} from "react";
import get from 'lodash/get'
import merge from 'lodash/merge'
import defaultLanguage from "./en_US.mjs";
import {isObject} from "@rjsf/utils";
import i18n from "../../../../core/components/translator"


function translateLocale(form, data, keys) {
    let newData = {}
    Object.entries(data).forEach(([k, v]) => {
        if (isObject(v) && !Array.isArray(v)) {
            newData[k] = translateLocale(form, v, [...(keys || []), k])
        } else {
            let token = `antd:::${[...(keys || []), k].join('.')}`
            let text = form.t(token)
            if (text !== token) {
                newData[k] = text
            } else {
                newData[k] = v
            }
        }
    })
    return newData
}

function useLocale() {
    const [locale, setLocale] = useState(defaultLanguage);

    function getLocale(path) {
        return get(locale, path)
    }

    function changeLocale(form, key) {
        i18n.loadNamespaces(['antd']).then(() => {
            let loc = merge({}, translateLocale(form, defaultLanguage), {language: key})
            setLocale(loc)
        })
    }

    return {locale, getLocale, changeLocale};
}

export const [useLocaleStore] = createGlobalStore(useLocale);
