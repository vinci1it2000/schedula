import {Spin} from 'antd';
import './Loader.css'

const Loader = ({spinning, children, ...props}) => {
    return (
        <Spin spinning={spinning} {...props}>
            {children}
        </Spin>
    );
};
export default Loader;