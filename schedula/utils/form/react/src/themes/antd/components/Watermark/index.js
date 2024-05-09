import {Watermark as BaseWatermark} from 'antd';

const Watermark = ({children, render, ...props}) => (
    <BaseWatermark {...props}>
        {children}
    </BaseWatermark>);
export default Watermark;