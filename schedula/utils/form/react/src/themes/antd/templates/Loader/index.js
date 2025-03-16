import {Spin} from 'antd';
const Loader = ({loading, children, ...props}) => {
    return <div className={'main-spin'} style={{height: '100%', width: '100%'}}>
        <Spin wrapperClassName={"full-height-spin"} spinning={loading} size="large"
              style={{maxHeight: null}} {...props}>
            {children}
        </Spin>
    </div>

};
export default Loader;