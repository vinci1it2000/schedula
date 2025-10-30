import React, {useEffect} from "react";
import {PlasmicRootProvider, DataProvider} from '@plasmicapp/loader-react';
import {Link as _Link} from "react-router-dom";
import {usePlasmicStore} from "../../models/plasmic";
import {Trans, useTranslation} from 'react-i18next';
// Defined as a hook; should be used and passed as translator
// prop to PlasmicRootProvider
function usePlasmicTranslator() {
    const {t} = useTranslation();
    return (key, opts) => {
        if (opts?.components) {
            return <Trans i18nKey={key} components={opts.components}/>;
        } else {
            return t(key, {defaultValue: opts.message});
        }
    };
}
function Link({href, ...props}) {
    return (
        <_Link to={href} {...props}></_Link>
    );
}
export default function ContentProvider(
    {
        form,
        children,
        options,
        ...props
    }
) {
    const {PLASMIC, setPlasmicOpts} = usePlasmicStore()
    useEffect(() => {
        setPlasmicOpts(options);
    }, [options]);
    const translator = usePlasmicTranslator()
    const {state: {language, userInfo = {}}} = form
    return PLASMIC ?
        <PlasmicRootProvider
            loader={PLASMIC}
            Link={Link}
            translator={translator}
            globalVariants={[{name: 'locale', value: language}]}
            {...props}
        >
            <DataProvider name={'form'} data={form}>
                <DataProvider name={'user'} data={{
                    id: null,
                    settings: null,
                    firstname: null,
                    lastname: null,
                    avatar: null,
                    email: null,
                    username: null,
                    custom_data: null,
                    roles: ['Anonymous'],
                    logged: userInfo?.id !== undefined && userInfo?.id !== null,
                    ...userInfo,
                }}>
                    <DataProvider name={'language'} data={language}>
                        {children}
                    </DataProvider>
                </DataProvider>
            </DataProvider>
        </PlasmicRootProvider> : children
}