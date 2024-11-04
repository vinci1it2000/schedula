import React, {useContext, useEffect, useState} from "react";
import {
    PlasmicComponent, PlasmicRootProvider
} from '@plasmicapp/loader-react';
import {usePlasmicStore} from "../../models/plasmic";
import {getTemplate, getUiOptions} from "@rjsf/utils";
import {useLocation} from "react-router-dom";


export default function PlasmicPage(
    {
        children,
        render,
        pathname,
        homePath = '/',
        componentProps,
        ...props
    }
) {
    const {uiSchema, registry, formContext: {FormContext}} = render
    const {form} = useContext(FormContext)
    const {PLASMIC} = usePlasmicStore()
    const [loading, setLoading] = useState(true);
    const [plasmicData, setPlasmicData] = useState(null);
    const uiOptions = getUiOptions(uiSchema);
    const Skeleton = getTemplate('Skeleton', registry, uiOptions);
    const NotFound = getTemplate('NotFound', registry, uiOptions);

    const {pathname: _pathname = '/'} = useLocation()

    pathname = pathname !== undefined ? pathname : _pathname
    useEffect(() => {
        async function load() {
            const plasmicData = await PLASMIC.maybeFetchComponentData(pathname);
            setPlasmicData(plasmicData);
            setLoading(false);
        }

        if (PLASMIC) {
            load();
        } else {
            setLoading(false)
        }
    }, [PLASMIC, pathname]);

    const content = plasmicData ?
        <div style={{overflowY: "auto", height: "100%"}}>
            <PlasmicRootProvider
                loader={PLASMIC}
                prefetchedData={plasmicData}
                pageRoute={plasmicData.entryCompMetas[0].path}
                pageParams={plasmicData.entryCompMetas[0].params}>
                <PlasmicComponent
                    component={plasmicData.entryCompMetas[0].displayName}
                    componentProps={{form, render, ...componentProps}}
                    {...props}/>
            </PlasmicRootProvider>
        </div> : (
            PLASMIC ?
                (
                    loading ?
                        <div style={{height: "100%", width: "100%"}}/> :
                        <NotFound homePath={homePath}/>
                ) :
                <div>PLASMIC not configured!</div>
        )
    return <Skeleton loading={loading} style={{padding: 16}} active>
        {content}
    </Skeleton>
}
