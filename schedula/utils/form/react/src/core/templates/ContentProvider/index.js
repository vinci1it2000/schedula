import React, {useEffect} from "react";
import {PlasmicRootProvider} from '@plasmicapp/loader-react';
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

export default function ContentProvider(
    {
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
    return PLASMIC ?
        <PlasmicRootProvider
            loader={PLASMIC}
            translator={translator} {...props}>
            {children}
        </PlasmicRootProvider> : children
}