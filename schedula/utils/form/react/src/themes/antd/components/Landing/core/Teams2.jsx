import React from 'react';
import QueueAnim from 'rc-queue-anim';
import {Row, Col} from 'antd';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import {getChildrenToRender, isImg} from './utils';

class Teams2 extends React.PureComponent {
    getBlockChildren = (data) =>
        data.map((item, i) => {
            const {titleWrapper, image, ...$item} = item;
            return (
                <Col key={i.toString()} {...$item}>
                    <Row>
                        <Col span={7}>
                            <div {...image}>
                                <img src={image.children} alt="img"/>
                            </div>
                        </Col>
                        <Col span={17}>
                            <QueueAnim {...titleWrapper} type="bottom">
                                {titleWrapper.children.map(getChildrenToRender)}
                            </QueueAnim>
                        </Col>
                    </Row>
                </Col>
            );
        });

    render() {
        const {...props} = this.props;
        const {dataSource} = props;
        delete props.dataSource;
        delete props.isMobile;
        const listChildren = this.getBlockChildren(dataSource.block.children);
        return (
            <div {...props} {...dataSource.wrapper}>
                <div {...dataSource.page}>
                    <div {...dataSource.titleWrapper}>
                        {dataSource.titleWrapper.children.map(getChildrenToRender)}
                    </div>
                    <OverPack {...dataSource.OverPack}>
                        <QueueAnim type="bottom" key="tween" leaveReverse>
                            <QueueAnim
                                type="bottom"
                                key="block"
                                {...dataSource.block}
                                component={Row}
                            >
                                {listChildren}
                            </QueueAnim>
                        </QueueAnim>
                    </OverPack>
                </div>
            </div>
        );
    }
}

export default Teams2;
