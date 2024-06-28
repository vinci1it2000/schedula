import React from "react";
import {ComponentWrapper} from "./core";


const CoreComponent = React.lazy(() => import('./core/Point'));

const Component = ({children, render, ...props}) => {
    return <ComponentWrapper
        render={render}
        CoreComponent={CoreComponent}
        {...props}>
        {children}
    </ComponentWrapper>
};
export default Component;