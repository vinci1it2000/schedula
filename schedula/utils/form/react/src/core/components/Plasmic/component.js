import React, {useContext, useEffect, useState} from "react";
import {
    PlasmicComponent as BasePlasmicComponent
} from '@plasmicapp/loader-react';
import {usePlasmicStore} from "../../models/plasmic";
import {getTemplate, getUiOptions} from "@rjsf/utils";

export default function PlasmicComponent(
    {
        children,
        render,
        component,
        componentProps,
        ...props
    }
) {
    const {uiSchema, registry, formContext: {FormContext}} = render
    const {form} = useContext(FormContext)
    const {PLASMIC} = usePlasmicStore()
    const [loading, setLoading] = useState(true);
    const [pageData, setPageData] = useState(null);
    const uiOptions = getUiOptions(uiSchema);
    const Skeleton = getTemplate('Skeleton', registry, uiOptions);
    useEffect(() => {
        async function load() {
            const pageData = await PLASMIC.maybeFetchComponentData(component);
            setPageData(pageData);
            setLoading(false);
        }

        if (PLASMIC) {
            load();
        } else {
            setLoading(false)
        }
    }, [PLASMIC, component]);
    const content = pageData ?
        <BasePlasmicComponent
            component={component}
            children={children}
            componentProps={{render, form, ...componentProps}}
            {...props}/> : (
            PLASMIC ?
                <div>Not found</div> :
                <div>PLASMIC not configured!</div>
        );
    return <Skeleton loading={loading} active>
        {content}
    </Skeleton>
}
