import React, {useEffect, useState} from "react";
import {PlasmicRootProvider, DataProvider} from '@plasmicapp/loader-react';
import {Link as _Link} from "react-router-dom";
import {usePlasmicStore} from "../../models/plasmic";
import {Trans, useTranslation} from 'react-i18next';

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
    return <_Link to={href} {...props} />;
}

export default function ContentProvider(
    {
        form,
        children,
        options,
        authProviderEndpoint = "/user/plasmic",
        ...props
    }
) {
    const {PLASMIC, setPlasmicOpts} = usePlasmicStore();
    const [plasmicAuth, setPlasmicAuth] = useState({user: null, token: null});

    useEffect(() => {
        setPlasmicOpts(options);
    }, [options]);

    // Fetch Plasmic user+token (server validated) once per session/page load
    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const res = await fetch(authProviderEndpoint, {credentials: "include"});
                const data = await res.json();
                if (!cancelled) setPlasmicAuth({
                    user: data.user ?? null,
                    token: data.token ?? null
                });
            } catch (e) {
                if (!cancelled) setPlasmicAuth({user: null, token: null});
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [authProviderEndpoint]);

    const translator = usePlasmicTranslator();
    const {state: {language, userInfo = {}}} = form;

    if (!PLASMIC) return children;

    return (
        <PlasmicRootProvider
            loader={PLASMIC}
            Link={Link}
            translator={translator}
            globalVariants={[{name: 'locale', value: language}]}

            // ✅ this is the key part
            user={plasmicAuth.user ?? undefined}
            userAuthToken={plasmicAuth.token ?? undefined}

            {...props}
        >
            <DataProvider name="form" data={form}>
                <DataProvider name="user" data={{
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
                    <DataProvider name="language" data={language}>
                        {children}
                    </DataProvider>
                </DataProvider>
            </DataProvider>
        </PlasmicRootProvider>
    );
}
