import React from "react";

const CoreComponent = React.lazy(() => import('./core/index'));
const Component = ({children, render, ...props}) => (
    <CoreComponent {...props}>
        {children}
    </CoreComponent>
);
export default Component;