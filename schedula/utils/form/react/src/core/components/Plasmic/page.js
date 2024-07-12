import React, {useEffect, useState} from "react";
import {
    PlasmicComponent
} from '@plasmicapp/loader-react';
import {usePlasmicStore} from "../../models/plasmic";
import {getTemplate, getUiOptions} from "@rjsf/utils";
import {useLocation} from "react-router-dom";


export default function PlasmicPage(
    {
        children,
        render: {uiSchema, registry},
        pathname,
        homePath = '/',
        ...props
    }
) {
    const {PLASMIC} = usePlasmicStore()
    const [loading, setLoading] = useState(true);
    const [pageData, setPageData] = useState(null);
    const uiOptions = getUiOptions(uiSchema);
    const Skeleton = getTemplate('Skeleton', registry, uiOptions);
    const NotFound = getTemplate('NotFound', registry, uiOptions);

    const {pathname: _pathname = '/'} = useLocation()

    pathname = pathname !== undefined ? pathname : _pathname
    useEffect(() => {
        async function load() {
            const pageData = await PLASMIC.maybeFetchComponentData(pathname);
            setPageData(pageData);
            setLoading(false);
        }

        if (PLASMIC) {
            load();
        } else {
            setLoading(false)
        }
    }, [PLASMIC, pathname]);
    const content = pageData ?
        <div style={{overflowY: "auto", height: "100%"}}>
            <PlasmicComponent component={pathname} {...props}/>
        </div> : (
            PLASMIC ?
                (
                    loading ?
                        <div style={{height: "100%", width: "100%"}}/> :
                        <NotFound homePath={homePath}/>
                ) :
                <div>PLASMIC not configured!</div>
        )
    return <Skeleton loading={loading} active>
        {content}
    </Skeleton>
}
