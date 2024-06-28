import React from "react";
import {ComponentWrapper} from "./core";
import {Pricing00DataSource as defaultDataSource} from './core/data.source';


const CoreComponent = React.lazy(() => import('./core/Pricing0'));

const Component = ({children, render, ...props}) => {
    return <ComponentWrapper
        render={render}
        CoreComponent={CoreComponent}
        defaultDataSource={defaultDataSource} {...props}>
        {children}
    </ComponentWrapper>
};
export default Component;