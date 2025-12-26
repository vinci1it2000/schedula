import React, {useContext, useEffect, useState, useMemo} from "react";
import {
    PageParamsProvider,
    PlasmicComponent,
} from '@plasmicapp/loader-react';
import {
    Routes,
    Route,
    useLocation,
    useSearchParams
} from 'react-router-dom';
import {usePlasmicStore} from "../../models/plasmic";
import {getTemplate, getUiOptions} from "@rjsf/utils";


export default function PlasmicPages(
    {
        children,
        render,
        homePath = '/',
        ...props
    }
) {
    const {uiSchema, registry, formContext: {FormContext}} = render
    const {form} = useContext(FormContext)
    const {PLASMIC} = usePlasmicStore()
    const uiOptions = getUiOptions(uiSchema);
    const {loadingPage, notFoundPage} = useMemo(() => {
        const Loader = getTemplate('Loader', registry, uiOptions);
        const NotFound = getTemplate('NotFound', registry, uiOptions);
        return {
            loadingPage: <Loader loading={true}>
                <div style={{height: "100%", width: "100%"}}/>
            </Loader>,
            notFoundPage: <NotFound homePath={homePath}/>,
        }
    }, [homePath, registry, uiOptions])
    return PLASMIC ?
        <Routes>
            <Route path="*" element={CatchAllPage({
                PLASMIC,
                form,
                render,
                loadingPage,
                notFoundPage,
            })}/>
            {children}
        </Routes> : <div>PLASMIC not configured!</div>

}

function CatchAllPage({PLASMIC, loadingPage, notFoundPage, form, render}) {
    const [loading, setLoading] = useState(true);
    const [pageData, setPageData] = useState(null);
    const location = useLocation();
    const searchParams = useSearchParams();

    useEffect(() => {
        async function load() {
            const pageData = await PLASMIC.maybeFetchComponentData(location.pathname);
            setPageData(pageData);
            setLoading(false);
        }

        load();
    }, [location.pathname]);

    if (loading) {
        return loadingPage
    }

    // The page will already be cached from the `load` call above.
    return (
        <PageParamsProvider
            route={pageData.entryCompMetas[0].path}
            params={pageData.entryCompMetas[0].params}
            query={Object.fromEntries(searchParams)}>
            {pageData ? <PlasmicComponent
                component={location.pathname}
                componentProps={{
                    form,
                    render
                }}/> : notFoundPage}
        </PageParamsProvider>
    );
}