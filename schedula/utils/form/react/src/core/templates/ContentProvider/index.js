import React, {useEffect} from "react";
import {PlasmicRootProvider} from '@plasmicapp/loader-react';
import {usePlasmicStore} from "../../models/plasmic";

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

    return PLASMIC ?
        <PlasmicRootProvider loader={PLASMIC} {...props}>
            {children}
        </PlasmicRootProvider> : children
}