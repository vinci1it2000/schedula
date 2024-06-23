import {ConfigProvider as BaseConfigProvider, notification, theme} from 'antd';
import {useQueryStore} from '../../models/query'
import React, {useEffect} from "react";
import {useLocaleStore} from "../../models/locale";

const ConfigProvider = (
    {
        children,
        dark,
        compact,
        form,
        theme: themeProps,
        element = BaseConfigProvider,
        ...props
    }) => {
    const {defaultAlgorithm, darkAlgorithm, compactAlgorithm} = theme;
    const {setQuery} = useQueryStore()
    const {state: {language}} = form
    const {changeLocale, locale} = useLocaleStore()
    useEffect(() => {
        changeLocale(form, language)
    }, [language])
    useEffect(() => {
        let params = {}
        const url = new URL(window.location.href);
        url.searchParams.forEach((value, key) => {
            params[key] = value
            url.searchParams.delete(key);
        });
        ['error', 'warning', 'success', 'info'].forEach(type => {
            const message = params[type]
            if (message) {
                notification[type]({message, placement: 'top'})
            }
        })
        setQuery(params)
        window.history.replaceState(null, null, url);
    }, [setQuery])
    let algorithm = [dark ? darkAlgorithm : defaultAlgorithm]
    if (compact)
        algorithm.push(compactAlgorithm)
    return React.createElement(element, {
        locale, theme: {
            algorithm,
            ...themeProps
        }, ...props
    }, children)
};
export default ConfigProvider;