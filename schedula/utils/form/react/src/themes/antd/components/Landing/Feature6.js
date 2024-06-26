import React from "react";
import merge from "lodash/merge";
import {useMultiValueContext} from "./core";
import {Feature60DataSource as defaultDataSource} from './core/data.source';
import {theme} from 'antd';

const {useToken} = theme

const CoreComponent = React.lazy(() => import('./core/Feature6'));

const Component = ({children, render, ...props}) => {
    const parentProps = useMultiValueContext();
    const _props = {
        ...merge({}, {dataSource: defaultDataSource}, parentProps), ...props
    }
    const {token} = useToken();
    return <CoreComponent style={{
        '--primary-color': token.colorPrimary,
        '--text-color': token.colorText
    }} {..._props}>
        {children}
    </CoreComponent>
};
export default Component;