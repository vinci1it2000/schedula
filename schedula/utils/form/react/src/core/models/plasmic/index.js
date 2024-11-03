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
        PLASMIC.registerComponent(withProps(component, {render}), {name, ...metaProps});
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

    return {PLASMIC, setPlasmicOpts, registerComponents};
}

export const [usePlasmicStore] = createGlobalStore(usePlasmic);
