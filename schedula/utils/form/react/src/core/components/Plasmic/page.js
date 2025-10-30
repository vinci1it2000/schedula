import React, {useContext, useEffect, useState, useMemo} from "react";
import {PlasmicComponent, PageParamsProvider} from '@plasmicapp/loader-react';
import {usePlasmicStore} from "../../models/plasmic";
import {getTemplate, getUiOptions} from "@rjsf/utils";
import {useLocation} from "react-router-dom";


export default function PlasmicPage(
    {
        children,
        render,
        pathname: path,
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
    const Loader = getTemplate('Loader', registry, uiOptions);
    const NotFound = getTemplate('NotFound', registry, uiOptions);
    const location = useLocation()
    const {
        pathname = '/',
        search,
        hash
    } = useMemo(() => {
        return path !== undefined ? new URL(path, window.location.origin) : location
    }, [path, location])
    const queryParams = new URLSearchParams(search);
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
            <PageParamsProvider
                route={plasmicData.entryCompMetas[0].path}
                params={plasmicData.entryCompMetas[0].params}
                query={Object.fromEntries(queryParams)}
            >
                <PlasmicComponent
                    component={plasmicData.entryCompMetas[0].displayName}
                    componentProps={{form, render, ...componentProps}}
                    {...props}
                />
            </PageParamsProvider>
        </div> : (
            PLASMIC ?
                (
                    loading ?
                        <div style={{height: "100%", width: "100%"}}/> :
                        <NotFound homePath={homePath}/>
                ) :
                <div>PLASMIC not configured!</div>
        )
    return <Loader loading={loading}>
        {content}
    </Loader>
}
