import {createGlobalStore} from "hox";
import {useState} from "react";
import get from 'lodash/get'
import assign from 'lodash/assign'
import defaultLanguage from "./en_US";

function useLocale() {
    const [locale, setLocale] = useState(defaultLanguage);

    function getLocale(path) {
        return get(locale, path)
    }

    function changeLocale(key) {
        import(`./${key}`).then((module) => {
            setLocale(assign({}, defaultLanguage, module.locale, {language: key}))
        });
    }

    return {locale, getLocale, changeLocale};
}

export const [useLocaleStore] = createGlobalStore(useLocale);
