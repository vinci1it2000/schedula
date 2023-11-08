import {ConfigProvider as BaseConfigProvider, notification, theme} from 'antd';
import 'ant-design-draggable-modal/dist/index.css'
import {useQueryStore} from '../../models/query'
import {useEffect} from "react";

const ConfigProvider = (
    {children, dark, compact, locale, theme: themeProps, ...props}) => {
    const {defaultAlgorithm, darkAlgorithm, compactAlgorithm} = theme;
    const {setQuery} = useQueryStore()
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
    return <BaseConfigProvider
        locale={locale}
        theme={{
            algorithm,
            ...themeProps
        }} {...props}>
        {children}
    </BaseConfigProvider>
};
export default ConfigProvider;