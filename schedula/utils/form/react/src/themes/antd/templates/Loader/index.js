import {Spin} from 'antd';

const Loader = ({spinning, children, ...props}) => {
    return <Spin spinning={spinning} size="large"
                 style={{maxHeight: null}} {...props}>
        {children}
    </Spin>

};
export default Loader;