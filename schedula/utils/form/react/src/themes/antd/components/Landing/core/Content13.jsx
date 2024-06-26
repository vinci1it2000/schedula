import React from 'react';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import QueueAnim from 'rc-queue-anim';
import {getChildrenToRender} from './utils';

class Content13 extends React.PureComponent {
    render() {
        const {...props} = this.props;
        const {dataSource} = props;
        delete props.dataSource;
        delete props.isMobile;
        return (
            <OverPack {...props} {...dataSource.OverPack}>
                <QueueAnim
                    type="bottom"
                    leaveReverse
                    key="page"
                    delay={[0, 100]}
                    {...dataSource.titleWrapper}
                >
                    {dataSource.titleWrapper.children.map(getChildrenToRender)}
                </QueueAnim>
            </OverPack>
        );
    }
}

export default Content13;
