import React from 'react';
import {createGlobalStore} from "hox";
import {useMemo, useState, useCallback} from "react";
import {initPlasmicLoader} from "@plasmicapp/loader-react";
import {getComponents} from "../../fields/utils";

function withProps(Component, extraProps) {
    return function PartiallyAppliedComponent(props) {
        return <Component {...extraProps} {...props} />;
    };
}

const registerPlasmicComponent = (PLASMIC, render, {
    component,
    meta: {name, ...metaProps}
}) => {
    if (typeof component === "string") {
        if (!name) name = component
        component = getComponents({render, component});
    }
    if (component)
        PLASMIC.registerComponent(withProps(component, {
            render,
            PLASMIC
        }), {name, ...metaProps});
}

const registerPlasmicComponents = (PLASMIC, render, components) => {
    if (PLASMIC && components) {
        if (!Array.isArray(components))
            components = [components]
        components.forEach((component) => {
            registerPlasmicComponent(PLASMIC, render, component);
        })
    }
}

const registerPlasmicGlobalContext = (PLASMIC, render, {
    context,
    meta: {name, ...metaProps}
}) => {
    if (typeof context === "string") {
        if (!name) name = context
        context = getComponents({render, component: context});
    }
    if (context)
        PLASMIC.registerGlobalContext(withProps(context, {
            render,
            PLASMIC
        }), {name, ...metaProps});
}

const registerPlasmicGlobalContexts = (PLASMIC, render, contexts) => {
    if (PLASMIC && contexts) {
        if (!Array.isArray(contexts))
            contexts = [contexts]
        contexts.forEach((context) => {
            registerPlasmicGlobalContext(PLASMIC, render, context);
        })
    }
}

const registerPlasmicTokens = (PLASMIC, render, tokens) => {
    if (PLASMIC && tokens) {
        if (!Array.isArray(tokens))
            tokens = [tokens]
        tokens.forEach((token) => {
            PLASMIC.registerToken(token)
        })
    }
}

function usePlasmic() {
    const [plasmicOpts, setPlasmicOpts] = useState(null)

    const PLASMIC = useMemo(() => {
        return plasmicOpts ? initPlasmicLoader(plasmicOpts) : undefined
    }, [plasmicOpts]);

    const registerComponents = useCallback((render, components) => {
        if (PLASMIC) {
            registerPlasmicComponents(PLASMIC, render, components)
        }
    }, [PLASMIC])

    const registerContexts = useCallback((render, contexts) => {
        if (PLASMIC) {
            registerPlasmicGlobalContexts(PLASMIC, render, contexts)
        }
    }, [PLASMIC])

    const registerTokens = useCallback((render, tokens) => {
        if (PLASMIC) {
            registerPlasmicTokens(PLASMIC, render, tokens)
        }
    }, [PLASMIC])

    return {
        PLASMIC,
        setPlasmicOpts,
        registerComponents,
        registerContexts,
        registerTokens
    };
}

export const [usePlasmicStore] = createGlobalStore(usePlasmic);
